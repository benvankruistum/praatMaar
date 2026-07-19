from __future__ import annotations

import threading

from modules.whisper import SharedWhisper


def test_try_locked_model_yields_none_when_busy() -> None:
    whisper = SharedWhisper()
    model = object()
    whisper.set_model(model)
    held = threading.Event()
    release = threading.Event()

    def hold_model() -> None:
        with whisper.locked_model():
            held.set()
            release.wait(timeout=2)

    holder = threading.Thread(target=hold_model)
    holder.start()
    assert held.wait(timeout=1)

    try:
        with whisper.try_locked_model() as acquired:
            assert acquired is None
    finally:
        release.set()
        holder.join(timeout=1)


def test_try_locked_model_yields_model_when_available() -> None:
    whisper = SharedWhisper()
    model = object()
    whisper.set_model(model)

    with whisper.try_locked_model() as acquired:
        assert acquired is model
