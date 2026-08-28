"""Lichte Qt-smoke voor de bestandstranscriptie-dialoog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from modules._builtin.file_transcription.dialog import show_file_transcription_dialog
from modules._builtin.file_transcription.jobs import FileBatchContext, FileTranscriptionQueue
from modules._contract import CycleEvent
from modules.whisper import SharedWhisper
from ui.app import ensure_app


class _Host:
    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def is_busy(self) -> bool:
        return False

    def transcribe_kwargs(self) -> dict:
        return {}

    def emit(self, event: CycleEvent) -> None:
        del event

    def capture_batch(self) -> FileBatchContext:
        return FileBatchContext(
            destination_name=None, save_discrete=lambda text: self._folder / "x.txt"
        )

    def destination_display(self) -> tuple[str | None, str]:
        return None, str(self._folder)

    def destinations(self) -> list[dict]:
        return []


def test_dialog_opens_via_helper(tmp_path: Path) -> None:
    ensure_app([])
    whisper = SharedWhisper()
    host = _Host(tmp_path)
    queue = FileTranscriptionQueue(
        whisper=whisper,
        host=host,
        decode_fn=lambda _path: None,
        sleep_fn=lambda _s: None,
    )
    dialog = show_file_transcription_dialog(queue=queue, host=host, existing=None)
    assert dialog.isVisible()
    again = show_file_transcription_dialog(queue=queue, host=host, existing=dialog)
    assert again is dialog
    dialog.close()
    for widget in QApplication.topLevelWidgets():
        widget.close()
