"""Registry- en actie-tests voor bestandstranscriptie."""

from __future__ import annotations

from modules._builtin.file_transcription import FileTranscriptionModule
from modules._contract import module_tray_actions
from modules.registry import all_builtin_modules
from ui.dialogs.modules import _EXPERIMENTAL_IDS


def test_file_transcription_is_builtin_and_default_off() -> None:
    module = next(m for m in all_builtin_modules() if m.id == "file-transcription")
    assert isinstance(module, FileTranscriptionModule)
    assert module.default_enabled() is False


def test_file_transcription_tray_action() -> None:
    module = FileTranscriptionModule()
    actions = module_tray_actions(module)
    assert len(actions) == 1
    assert actions[0].id == "transcribe_files"
    assert actions[0].in_tray is True
    assert actions[0].in_tray_root is False


def test_file_transcription_experimental_badge_uses_kebab_id() -> None:
    assert "file-transcription" in _EXPERIMENTAL_IDS
    assert "meeting-buddy" in _EXPERIMENTAL_IDS
    assert "local-llm" in _EXPERIMENTAL_IDS
