"""Tests voor de begrensde continuous-capture-ringbuffer."""

from __future__ import annotations

import numpy as np

from modules._builtin.audio_capture import CaptureGap, RingBuffer


def test_overflow_emits_gap_and_drops_oldest() -> None:
    buf = RingBuffer(max_duration_s=0.05, sample_rate=16_000)
    gaps: list[CaptureGap] = []
    buf.on_gap = gaps.append

    samples = np.zeros(16_000, dtype=np.float32)
    buf.write(samples, start_ms=0)

    assert gaps, "expected CaptureGap on overflow"
    assert gaps == [
        CaptureGap(
            session_id="",
            start_ms=0,
            end_ms=950,
            reason="ring_buffer_overflow",
        )
    ]
    assert buf.available_samples == 800


def test_read_window_retains_overlap_for_next_chunk() -> None:
    buf = RingBuffer(max_duration_s=10, sample_rate=16_000)
    first_samples = np.arange(48_000, dtype=np.float32)
    buf.write(first_samples, start_ms=0)

    first = buf.read_window(sample_count=48_000, retain_samples=8_000)
    buf.write(np.arange(48_000, 88_000, dtype=np.float32), start_ms=3_000)
    second = buf.read_window(sample_count=48_000, retain_samples=8_000)

    assert first is not None
    assert first.start_ms == 0
    assert np.array_equal(first.samples, first_samples)
    assert second is not None
    assert second.start_ms == 2_500
    assert second.samples[0] == 40_000
