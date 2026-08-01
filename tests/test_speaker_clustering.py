"""Unit tests for online single-mic speaker clustering."""

from __future__ import annotations

import numpy as np

from modules._builtin.speaker_clustering import OnlineSpeakerCluster
from modules._builtin.speaker_detection import SpeakerDetectionService
from modules.capabilities.speaker_detection import (
    AudioSource,
    LabelingMode,
    SpeakerRole,
    TranscriptSegment,
)


def _tone(freq: float, duration_s: float, sr: int = 16000, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(sr * duration_s), dtype=np.float32) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_cluster_assigns_stable_speaker_ids_for_distinct_tones() -> None:
    cluster = OnlineSpeakerCluster()
    cluster.start_session("m1")
    # Two alternating “speakers” as different tones with silence between.
    sr = 16000
    parts: list[np.ndarray] = []
    cursor_ms = 0
    for freq in [220.0, 880.0, 220.0, 880.0]:
        speech = _tone(freq, 0.6, sr=sr)
        silence = np.zeros(int(sr * 0.35), dtype=np.float32)
        chunk = np.concatenate([speech, silence])
        start_ms = cursor_ms
        end_ms = start_ms + int(len(chunk) * 1000 / sr)
        cluster.observe_pcm("m1", chunk.tobytes(), start_ms, end_ms, sr)
        cursor_ms = end_ms
        parts.append(chunk)

    a = cluster.assign("m1", 0, 500)
    b = cluster.assign("m1", 1000, 1500)
    c = cluster.assign("m1", 2000, 2500)
    d = cluster.assign("m1", 3000, 3500)
    assert a is not None and b is not None and c is not None and d is not None
    assert a.speaker_id.startswith("spk_")
    assert b.speaker_id.startswith("spk_")
    assert a.speaker_id == c.speaker_id
    assert b.speaker_id == d.speaker_id
    assert a.speaker_id != b.speaker_id


def test_service_cluster_mode_never_returns_me() -> None:
    service = SpeakerDetectionService()
    service.start_session("m1")
    service.set_labeling_mode("m1", LabelingMode.CLUSTER)
    sr = 16000
    pcm = _tone(440.0, 0.8, sr=sr)
    service.observe_pcm("m1", pcm.tobytes(), 0, int(len(pcm) * 1000 / sr), sr)
    assignment = service.assign_speaker(
        TranscriptSegment(
            text="hallo allemaal",
            session_id="m1",
            source=AudioSource.MICROPHONE,
            start_ms=0,
            end_ms=500,
        )
    )
    assert assignment.role == SpeakerRole.OTHER
    assert assignment.speaker_id.startswith("spk_")
    assert assignment.role != SpeakerRole.ME


def test_service_source_mode_still_maps_microphone_to_me() -> None:
    service = SpeakerDetectionService()
    service.start_session("s1")
    service.set_labeling_mode("s1", LabelingMode.SOURCE)
    assignment = service.assign_speaker(
        TranscriptSegment(text="ik", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert assignment.role == SpeakerRole.ME
    assert assignment.speaker_id == "me"
