"""Tests voor SharedWhisper — gedeeld Faster-Whisper-model voor modules + dicteren."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from modules._contract import ModuleContext, noop_ui_dispatch
from modules.whisper import SharedWhisper


class _FakeModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def transcribe(self, path: str, **_kwargs: object) -> tuple[list[object], object]:
        self.calls.append(path)
        return [], object()


def test_shared_whisper_not_ready_until_model_set() -> None:
    whisper = SharedWhisper()
    assert whisper.is_ready is False
    assert whisper.model is None


def test_shared_whisper_set_model_makes_ready() -> None:
    whisper = SharedWhisper()
    fake = _FakeModel()
    whisper.set_model(fake)
    assert whisper.is_ready is True
    assert whisper.model is fake


def test_locked_model_raises_when_not_ready() -> None:
    whisper = SharedWhisper()
    with pytest.raises(RuntimeError, match="niet geladen"):
        with whisper.locked_model():
            pass


def test_locked_model_yields_model_under_lock() -> None:
    whisper = SharedWhisper()
    fake = _FakeModel()
    whisper.set_model(fake)

    with whisper.locked_model() as model:
        assert model is fake
        model.transcribe("x.wav")

    assert fake.calls == ["x.wav"]


def test_module_context_exposes_shared_whisper(tmp_path: Path) -> None:
    whisper = SharedWhisper()
    ctx = ModuleContext(
        app_dir=tmp_path,
        ui_dispatch=noop_ui_dispatch,
        whisper=whisper,
    )
    assert ctx.whisper is whisper


def test_locked_model_serializes_across_threads() -> None:
    """Dicteren en modules moeten dezelfde lock delen (serialisatie)."""

    whisper = SharedWhisper()
    whisper.set_model(_FakeModel())
    order: list[str] = []
    started = threading.Event()
    done_first = threading.Event()

    def first() -> None:
        with whisper.locked_model():
            order.append("a-enter")
            started.set()
            done_first.wait(timeout=2)
            order.append("a-leave")

    def second() -> None:
        started.wait(timeout=2)
        with whisper.locked_model():
            order.append("b-enter")
            order.append("b-leave")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    # Geef second kans om te blokkeren op de lock.
    threading.Event().wait(0.05)
    done_first.set()
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert order == ["a-enter", "a-leave", "b-enter", "b-leave"]
