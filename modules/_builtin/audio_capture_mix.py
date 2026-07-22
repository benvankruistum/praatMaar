"""Resample and mix helpers for continuous audio capture."""

from __future__ import annotations

import numpy as np

TARGET_SAMPLE_RATE = 16_000


def stereo_to_mono(samples: np.ndarray) -> np.ndarray:
    """Downmix multi-channel float32 samples to mono."""

    arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim == 1:
        return arr.reshape(-1)
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0]
        return arr.mean(axis=1, dtype=np.float32)
    return arr.reshape(-1)


def resample_mono(
    samples: np.ndarray,
    *,
    from_rate: int,
    to_rate: int = TARGET_SAMPLE_RATE,
) -> np.ndarray:
    """Linear resample mono float32 audio to the capture target rate."""

    mono = np.asarray(samples, dtype=np.float32).reshape(-1)
    if mono.size == 0 or from_rate <= 0 or from_rate == to_rate:
        return mono

    target_len = max(1, int(round(mono.size * to_rate / from_rate)))
    source_x = np.linspace(0.0, 1.0, num=mono.size, endpoint=False)
    target_x = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
    return np.interp(target_x, source_x, mono).astype(np.float32)


def mix_mono_chunks(mic: np.ndarray, loopback: np.ndarray) -> np.ndarray:
    """Mix two mono chunks of equal length with headroom."""

    length = min(mic.size, loopback.size)
    if length <= 0:
        return np.empty(0, dtype=np.float32)
    mixed = 0.5 * mic[:length] + 0.5 * loopback[:length]
    return np.clip(mixed, -1.0, 1.0).astype(np.float32)
