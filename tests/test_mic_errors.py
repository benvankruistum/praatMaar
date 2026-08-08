"""Tests voor gebruikersvriendelijke microfoonfouten."""

from __future__ import annotations

import i18n
from mic_errors import (
    classify_mic_error,
    device_identity,
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


def test_device_identity_default_input() -> None:
    class FakeSd:
        @staticmethod
        def query_devices(*, kind: str | None = None, **_kwargs):
            assert kind == "input"
            return {"name": "Default Mic", "hostapi": 0}

    assert device_identity(FakeSd(), None) == ("Default Mic", 0)


def test_device_identity_pinned_index() -> None:
    class FakeSd:
        @staticmethod
        def query_devices(device=None, **_kwargs):
            assert device == 3
            return {"name": "Headset", "hostapi": 1}

    assert device_identity(FakeSd(), 3) == ("Headset", 1)


def test_device_identity_invalid_returns_none() -> None:
    class FakeSd:
        @staticmethod
        def query_devices(*_args, **_kwargs):
            raise RuntimeError("missing")

    assert device_identity(FakeSd(), 9) is None


def test_device_identity_empty_name_returns_none() -> None:
    class FakeSd:
        @staticmethod
        def query_devices(*_args, **_kwargs):
            return {"name": "", "hostapi": 0}

    assert device_identity(FakeSd(), None) is None
