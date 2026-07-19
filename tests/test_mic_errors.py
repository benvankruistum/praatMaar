"""Tests voor gebruikersvriendelijke microfoonfouten."""

from __future__ import annotations

import i18n
from mic_errors import (
    classify_mic_error,
    first_input_device_index,
    format_recording_start_error,
    has_input_device,
    refresh_portaudio,
)


def test_classify_querying_device_minus_one() -> None:
    assert (
        classify_mic_error(RuntimeError("Error querying device -1"))
        == "rec.mic_default_unavailable"
    )


def test_classify_invalid_device() -> None:
    assert classify_mic_error(
        RuntimeError("Error opening InputStream: Invalid device [-9996]")
    ) == ("rec.mic_invalid")


def test_format_includes_checklist(monkeypatch) -> None:
    i18n.set_ui_language("nl")
    monkeypatch.setattr("mic_errors.sys.platform", "win32")
    text = format_recording_start_error(RuntimeError("No Default Input Device Available"))
    assert "geen microfoon" in text.lower() or "geen microfoon" in text
    assert "Privacy" in text or "privacy" in text.lower()
    assert "Technische details" in text
    assert "No Default Input Device Available" in text


def test_has_input_device_false() -> None:
    class FakeSd:
        @staticmethod
        def query_devices():
            return [{"name": "speakers", "max_input_channels": 0}]

    assert has_input_device(FakeSd()) is False


def test_has_input_device_true() -> None:
    class FakeSd:
        @staticmethod
        def query_devices():
            return [{"name": "mic", "max_input_channels": 1}]

    assert has_input_device(FakeSd()) is True


def test_first_input_device_index() -> None:
    class FakeSd:
        @staticmethod
        def query_devices():
            return [
                {"name": "out", "max_input_channels": 0},
                {"name": "mic", "max_input_channels": 1},
            ]

    assert first_input_device_index(FakeSd()) == 1


def test_refresh_portaudio_reinitializes() -> None:
    calls: list[str] = []

    class FakeSd:
        _initialized = 2

        @classmethod
        def _terminate(cls) -> None:
            calls.append("term")
            cls._initialized -= 1

        @classmethod
        def _initialize(cls) -> None:
            calls.append("init")
            cls._initialized += 1

    refresh_portaudio(FakeSd)
    assert calls == ["term", "term", "init"]
    assert FakeSd._initialized == 1
