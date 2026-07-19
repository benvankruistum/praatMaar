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
        self._model: Any | None = None

    @property
    def model(self) -> Any | None:
        return self._model

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def lock(self) -> threading.Lock:
        """Dezelfde lock als ``locked_model`` — voor geavanceerde callers."""

        return self._lock

    def set_model(self, model: Any | None) -> None:
        """Zet of wist het gedeelde model (na splash / modelwissel)."""

        with self._lock:
            self._model = model

    @contextmanager
    def locked_model(self) -> Iterator[Any]:
        """
        Levert het model onder de gedeelde lock.

        Raises:
            RuntimeError: als het model nog niet geladen is.
        """

        with self._lock:
            if self._model is None:
                raise RuntimeError("Whisper-model is niet geladen.")
            yield self._model
