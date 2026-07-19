"""Tests voor dictation.retranscribe_recovery_wav (gemockt model)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import dictation
import recovery


class _FakeSession:
    def __init__(self, *, recording: bool = False, processing: bool = False) -> None:
        self.is_recording = recording
        self.is_processing = processing


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls: list[str] = []

    def transcribe(self, path: str, **_kwargs):
        self.calls.append(path)
        return ([_FakeSegment(t) for t in self._texts], SimpleNamespace())


def test_retranscribe_busy_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(dictation, "session", _FakeSession(recording=True))
    dictation.shared_whisper.set_model(object())
    with pytest.raises(RuntimeError, match=".+"):
        dictation.retranscribe_recovery_wav(tmp_path / "x.wav")


def test_retranscribe_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    directory = tmp_path / "recovery"
    directory.mkdir()
    wav = directory / "2026-01-01_120000.wav"
    wav.write_bytes(b"RIFF")

    fake_model = _FakeModel(["Hallo", "wereld"])
    pasted: list[str] = []
    copied: list[str] = []

    monkeypatch.setattr(dictation, "session", _FakeSession())
    dictation.shared_whisper.set_model(fake_model)
    monkeypatch.setattr(dictation, "LANGUAGE", "nl")
    monkeypatch.setattr(dictation, "AUTO_PASTE", True)
    monkeypatch.setattr(dictation, "wait_until_modifier_keys_released", lambda: None)
    monkeypatch.setattr(dictation, "PASTE_DELAY_SECONDS", 0)
    monkeypatch.setattr(dictation, "_copy_to_clipboard", lambda text: copied.append(text))
    monkeypatch.setattr(dictation.host, "paste", lambda: pasted.append("ok"))
    monkeypatch.setattr(dictation, "ACTIVE_DESTINATION", None)
    monkeypatch.setattr(dictation, "DESTINATIONS", [])

    text = dictation.retranscribe_recovery_wav(wav)
    assert text == "Hallo wereld"
    assert copied == ["Hallo wereld"]
    assert pasted == ["ok"]
    assert fake_model.calls == [str(wav.resolve())]
    assert list((tmp_path / "transcripts").glob("*.txt"))


def test_retranscribe_rejects_outside_recovery(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    (tmp_path / "recovery").mkdir()
    outsider = tmp_path / "other.wav"
    outsider.write_bytes(b"x")
    monkeypatch.setattr(dictation, "session", _FakeSession())
    dictation.shared_whisper.set_model(_FakeModel(["hi"]))
    with pytest.raises(ValueError):
        dictation.retranscribe_recovery_wav(outsider)
