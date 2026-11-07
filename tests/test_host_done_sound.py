"""Systeemklank na transcriptie: padkeuze, zonder echt geluid."""

from __future__ import annotations

from pathlib import Path

import pytest

from host._done_sound import play_command
from host._win import windows_completion_wav


def test_windows_completion_wav_picks_the_first_present_ding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "Media"
    media.mkdir()
    (media / "Windows Notify.wav").write_bytes(b"notify")
    (media / "Windows Ding.wav").write_bytes(b"ding")
    monkeypatch.setenv("WINDIR", str(tmp_path))

    assert windows_completion_wav() == media / "Windows Ding.wav"


def test_windows_completion_wav_is_none_when_media_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINDIR", str(tmp_path))
    assert windows_completion_wav() is None


def test_play_command_swallows_a_missing_player(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(command: list[str], **kwargs: object) -> None:
        raise OSError("afplay ontbreekt")

    monkeypatch.setattr("host._done_sound.subprocess.Popen", boom)
    play_command(["afplay", "-v", "0.4", "Glass.aiff"])
