"""
Gedeeld Faster-Whisper-model voor dicteercyclus én in-process modules.

Eén geladen model + één lock: voorkomt dubbele RAM/VRAM-belasting als een
module (bijv. Meeting Buddy) ook transcribeert. Geen sessie-lifecycle —
modules houden eigen opname/chunking; dit is alleen modeltoegang.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class SharedWhisper:
    """Bron van waarheid voor het geladen Whisper-model en de model-lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._priority_lock = threading.Lock()
        self._dictation_count = 0
        self._model: Any | None = None

    @property
    def model(self) -> Any | None:
        return self._model

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def dictation_active(self) -> bool:
        """Of dicteren Whisper gebruikt of op de model-lock wacht."""

        with self._priority_lock:
            return self._dictation_count > 0

    @property
    def lock(self) -> threading.Lock:
        """Dezelfde lock als ``locked_model`` — voor geavanceerde callers."""

        return self._lock

    def set_model(self, model: Any | None) -> None:
        """Zet of wist het gedeelde model (na splash / modelwissel)."""

        with self._lock:
            self._model = model

    @contextmanager
    def dictation_priority(self) -> Iterator[None]:
        """Markeert nesting-safe dat dicteren voorrang nodig heeft."""

        with self._priority_lock:
            self._dictation_count += 1
        try:
            yield
        finally:
            with self._priority_lock:
                self._dictation_count -= 1

    @contextmanager
    def locked_model(self) -> Iterator[Any]:
        """
        Levert het model onder de gedeelde lock.

        Raises:
            RuntimeError: als het model nog niet geladen is.
        """

        with self.dictation_priority():
            with self._lock:
                if self._model is None:
                    raise RuntimeError("Whisper-model is niet geladen.")
                yield self._model

    @contextmanager
    def try_locked_model(self, timeout: float = 0.0) -> Iterator[Any | None]:
        """Levert het model, of ``None`` als de lock niet tijdig beschikbaar is."""

        if self.dictation_active:
            yield None
            return
        acquired = self._lock.acquire(timeout=timeout)
        if not acquired:
            yield None
            return
        try:
            yield self._model
        finally:
            self._lock.release()
