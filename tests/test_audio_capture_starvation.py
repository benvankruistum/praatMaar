"""Mix-starvation: een dode loopback-bron mag de capture niet stilleggen."""

from __future__ import annotations

from threading import Event

import numpy as np

from modules._builtin.audio_capture import (
    SAMPLE_RATE,
    AudioCaptureEngine,
    RingBuffer,
    _CaptureState,
)


def _state(*, loopback_enabled: bool) -> _CaptureState:
    return _CaptureState(
        session_id="s1",
        buffer=RingBuffer(max_duration_s=30.0, sample_rate=SAMPLE_RATE),
        stop_event=Event(),
        handlers=[],
        loopback_enabled=loopback_enabled,
        loopback_requested=loopback_enabled,
    )


def test_starved_loopback_falls_back_to_mic_only() -> None:
    # Regression: levert de loopback-stream geen data (WASAPI zonder
    # renderende audio, device-glitch zonder disconnect), dan mixte
    # _flush_mixed_samples niets (count=0) en groeide mic_pending onbegrensd
    # — meeting leek actief maar het transcript bleef leeg.
    engine = AudioCaptureEngine(sounddevice_module=object())
    state = _state(loopback_enabled=True)

    six_seconds = np.zeros(SAMPLE_RATE * 6, dtype=np.float32)
    engine._append_mic_samples(state, six_seconds)

    assert state.loopback_enabled is False, "starved loopback moet uitschakelen (mic-only)"
    assert state.mic_pending.size == 0, "mic-backlog moet daarna doorstromen"
    assert state.captured_samples == six_seconds.size


def test_loopback_pending_is_bounded_without_mic_data() -> None:
    engine = AudioCaptureEngine(sounddevice_module=object())
    state = _state(loopback_enabled=True)

    ten_seconds = np.zeros(SAMPLE_RATE * 10, dtype=np.float32)
    engine._append_loopback_samples(state, ten_seconds)

    assert state.loopback_pending.size <= SAMPLE_RATE * 5
