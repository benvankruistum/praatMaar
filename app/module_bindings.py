"""Composition-root bindings for modules that need dicteercyclus-adjacent hosts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import destinations
import recovery
from app.recovery_actions import save_transcript_discrete
from modules._builtin.file_transcription.jobs import FileBatchContext
from modules._contract import CycleEvent, PraatMaarModule


class RuntimeFileJobHost:
    """FileJobHost gebonden aan de live Opnamesessie / bestemmingen / ModuleBus."""

    def __init__(
        self,
        *,
        session_fn: Callable[[], Any],
        destinations_fn: Callable[[], Sequence[dict[str, Any]]],
        active_destination_fn: Callable[[], str | None],
        emit: Callable[[CycleEvent], None],
    ) -> None:
        self._session_fn = session_fn
        self._destinations_fn = destinations_fn
        self._active_destination_fn = active_destination_fn
        self._emit = emit

    def is_busy(self) -> bool:
        session = self._session_fn()
        return bool(
            getattr(session, "is_recording", False) or getattr(session, "is_processing", False)
        )

    def transcribe_kwargs(self) -> dict[str, Any]:
        session = self._session_fn()
        getter = getattr(session, "transcribe_kwargs", None)
        if callable(getter):
            return dict(getter())
        return {}

    def emit(self, event: CycleEvent) -> None:
        self._emit(event)

    def destinations(self) -> list[dict[str, Any]]:
        return list(self._destinations_fn())

    def destination_display(self) -> tuple[str | None, str]:
        name = self._active_destination_fn()
        directory = destinations.resolve_save_dir(
            name,
            self.destinations(),
            recovery.transcripts_dir(),
        )
        return name, str(directory)

    def capture_batch(self) -> FileBatchContext:
        name = self._active_destination_fn()
        dests = self.destinations()

        def save(text: str) -> Path:
            return save_transcript_discrete(
                text,
                active_destination=name,
                destinations_list=dests,
            )

        return FileBatchContext(destination_name=name, save_discrete=save)


def bind_file_transcription(
    modules: Sequence[PraatMaarModule],
    *,
    session_fn: Callable[[], Any],
    destinations_fn: Callable[[], Sequence[dict[str, Any]]],
    active_destination_fn: Callable[[], str | None],
    emit: Callable[[CycleEvent], None],
) -> None:
    host = RuntimeFileJobHost(
        session_fn=session_fn,
        destinations_fn=destinations_fn,
        active_destination_fn=active_destination_fn,
        emit=emit,
    )
    for module in modules:
        binder = getattr(module, "bind_file_host", None)
        if callable(binder):
            binder(host)
