"""Bestandstranscriptie builtin module."""

from __future__ import annotations

from modules._builtin.file_transcription.jobs import FileJobHost, FileTranscriptionQueue
from modules._contract import CycleEvent, ModuleAction, ModuleContext
from modules.whisper import SharedWhisper


class FileTranscriptionModule:
    id = "file-transcription"

    def __init__(self) -> None:
        self._whisper: SharedWhisper | None = None
        self._ui_dispatch = None
        self._host: FileJobHost | None = None
        self._queue: FileTranscriptionQueue | None = None
        self._dialog = None

    def display_name_key(self) -> str:
        return "modules.file_transcription.name"

    def description_key(self) -> str:
        return "modules.file_transcription.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._whisper = ctx.whisper
        self._ui_dispatch = ctx.ui_dispatch

    def on_event(self, event: CycleEvent) -> None:
        del event

    def bind_file_host(self, host: FileJobHost) -> None:
        self._host = host
        if self._whisper is None:
            return
        self._queue = FileTranscriptionQueue(
            whisper=self._whisper,
            host=host,
            on_change=self._on_queue_change,
        )

    def on_app_shutdown(self) -> None:
        if self._queue is not None:
            self._queue.shutdown()
        dialog = self._dialog
        self._dialog = None
        if dialog is not None and self._ui_dispatch is not None:
            self._ui_dispatch(dialog.close)

    def actions(self) -> list[ModuleAction]:
        return [
            ModuleAction(
                id="transcribe_files",
                label_key="modules.file_transcription.actions.transcribe",
                handler=self.open_dialog,
                in_tray=True,
            )
        ]

    def open_dialog(self) -> None:
        if self._ui_dispatch is None:
            return
        self._ui_dispatch(self._show_dialog)

    def _show_dialog(self) -> None:
        from modules._builtin.file_transcription.dialog import show_file_transcription_dialog

        if self._queue is None or self._host is None:
            return
        self._dialog = show_file_transcription_dialog(
            queue=self._queue,
            host=self._host,
            existing=self._dialog,
        )

    def _on_queue_change(self) -> None:
        dialog = self._dialog
        dispatch = self._ui_dispatch
        if dialog is None or dispatch is None:
            return
        dispatch(dialog.refresh)
