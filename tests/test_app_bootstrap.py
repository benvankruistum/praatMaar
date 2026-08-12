"""AppRuntime bootstrap: geen import-time Opnamesessie."""

from __future__ import annotations

from app.bootstrap import build_runtime, build_session
from app.runtime import AppRuntime
from modules import CapabilityRegistry, ModuleBus, SharedWhisper


class FakeHost:
    def paste(self) -> None:
        pass


def test_build_runtime_has_no_session() -> None:
    runtime = build_runtime(host_obj=FakeHost())
    assert isinstance(runtime, AppRuntime)
    assert runtime.session is None
    assert isinstance(runtime.shared_whisper, SharedWhisper)
    assert isinstance(runtime.capability_registry, CapabilityRegistry)
    assert isinstance(runtime.module_bus, ModuleBus)


def test_build_session_constructs_once() -> None:
    runtime = build_runtime(host_obj=FakeHost(), mode="toggle", language="nl")
    assert runtime.session is None
    session = build_session(runtime)
    assert runtime.session is session
    assert session.mode == "toggle"
    assert session.language == "nl"


def test_dictation_session_is_lazy(monkeypatch) -> None:
    """``import dictation`` bouwt geen Opnamesessie; eerste access wel."""

    import dictation

    constructed: list[int] = []
    real_build = dictation._build_session

    def tracking_build():
        constructed.append(1)
        return real_build()

    monkeypatch.setattr(dictation, "_build_session", tracking_build)
    monkeypatch.setattr(dictation, "_session", None)
    dictation.__dict__.pop("session", None)

    assert constructed == []
    _ = dictation.session
    assert constructed == [1]
