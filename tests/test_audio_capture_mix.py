"""Tests for audio capture mixing helpers."""

from __future__ import annotations

import numpy as np

from modules._builtin.audio_capture_mix import mix_mono_chunks, resample_mono, stereo_to_mono


def test_stereo_to_mono_averages_channels() -> None:
    stereo = np.array([[1.0, -1.0], [0.5, 0.5]], dtype=np.float32)
    assert np.allclose(stereo_to_mono(stereo), [0.0, 0.5])


def test_resample_mono_downsamples() -> None:
    samples = np.ones(4800, dtype=np.float32)
    resampled = resample_mono(samples, from_rate=48000, to_rate=16000)
    assert resampled.size == 1600


def test_mix_mono_chunks_clips() -> None:
    mic = np.array([1.0, 1.0], dtype=np.float32)
    loopback = np.array([1.0, 1.0], dtype=np.float32)
    mixed = mix_mono_chunks(mic, loopback)
    assert mixed.max() <= 1.0
    assert mixed.min() >= -1.0


def test_mix_mono_chunks_respects_gains() -> None:
    mic = np.array([1.0, 0.0], dtype=np.float32)
    loopback = np.array([0.0, 1.0], dtype=np.float32)
    mixed = mix_mono_chunks(mic, loopback, mic_gain=1.0, loopback_gain=0.0)
    assert np.allclose(mixed, [1.0, 0.0])
    mixed = mix_mono_chunks(mic, loopback, mic_gain=0.0, loopback_gain=1.0)
    assert np.allclose(mixed, [0.0, 1.0])
