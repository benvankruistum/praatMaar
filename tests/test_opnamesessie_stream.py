"""Tests voor warm_microphone / macOS stream-gedrag."""

from __future__ import annotations

from opnamesessie import Opnamesessie


class _FakeHost:
    def paste(self) -> None:
        return None


def test_keep_stream_warm_off_on_darwin_even_if_requested(monkeypatch) -> None:
    monkeypatch.setattr("opnamesessie.sys.platform", "darwin")
    session = Opnamesessie(host=_FakeHost(), warm_microphone=True)
    assert session.warm_microphone is True
    assert session._keep_stream_warm() is False


def test_keep_stream_warm_respects_setting_on_windows(monkeypatch) -> None:
    monkeypatch.setattr("opnamesessie.sys.platform", "win32")
    cold = Opnamesessie(host=_FakeHost(), warm_microphone=False)
    warm = Opnamesessie(host=_FakeHost(), warm_microphone=True)
    assert cold._keep_stream_warm() is False
    assert warm._keep_stream_warm() is True


def test_warmup_skipped_on_darwin(monkeypatch) -> None:
    monkeypatch.setattr("opnamesessie.sys.platform", "darwin")
    session = Opnamesessie(host=_FakeHost(), warm_microphone=True)
    called = {"n": 0}

    def boom() -> None:
        called["n"] += 1
        raise AssertionError("stream mag niet openen op macOS-warmup")

    session._ensure_stream = boom  # type: ignore[method-assign]
    session.warmup_microphone()
    assert called["n"] == 0
