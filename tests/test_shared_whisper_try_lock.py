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


def test_dictation_wins_when_priority_starts_during_buddy_acquire() -> None:
    whisper = SharedWhisper()
    whisper.set_model(object())
    about_to_acquire = threading.Event()
    continue_acquire = threading.Event()
    buddy_finished = threading.Event()
    dictation_acquired = threading.Event()
    buddy_result: list[object | None] = []
    real_lock = whisper._lock

    class PausedBuddyLock:
        def acquire(self, timeout: float = -1) -> bool:
            if threading.current_thread().name == "buddy":
                about_to_acquire.set()
                assert continue_acquire.wait(timeout=2)
            return real_lock.acquire(timeout=timeout)

        def release(self) -> None:
            real_lock.release()

        def __enter__(self) -> PausedBuddyLock:
            self.acquire()
            return self

        def __exit__(self, *_args: object) -> None:
            self.release()

    whisper._lock = PausedBuddyLock()  # type: ignore[assignment]

    def run_buddy() -> None:
        with whisper.try_locked_model() as acquired:
            buddy_result.append(acquired)
        buddy_finished.set()

    def run_dictation() -> None:
        assert about_to_acquire.wait(timeout=1)
        with whisper.dictation_priority():
            continue_acquire.set()
            assert buddy_finished.wait(timeout=1)
            with whisper.locked_model():
                dictation_acquired.set()

    buddy = threading.Thread(target=run_buddy, name="buddy")
    dictation = threading.Thread(target=run_dictation, name="dictation")
    buddy.start()
    dictation.start()
    buddy.join(timeout=2)
    dictation.join(timeout=2)

    assert not buddy.is_alive()
    assert not dictation.is_alive()
    assert buddy_result == [None]
    assert dictation_acquired.is_set()


def test_dictation_priority_is_nesting_safe() -> None:
    whisper = SharedWhisper()

    assert whisper.dictation_active is False
    with whisper.dictation_priority():
        assert whisper.dictation_active is True
        with whisper.dictation_priority():
            assert whisper.dictation_active is True
        assert whisper.dictation_active is True
    assert whisper.dictation_active is False
