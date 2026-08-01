"""Lightweight online speaker clustering for single-mic meetings (local-only)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_FRAME_MS = 25
_HOP_MS = 10
_MIN_SPEECH_MS = 200
_SILENCE_END_MS = 250
_ENERGY_FLOOR = 1e-4
_NEW_SPEAKER_THRESHOLD = 0.72
_N_BANDS = 16


@dataclass(frozen=True)
class ClusterHit:
    speaker_id: str
    confidence: float


@dataclass
class _Span:
    start_ms: int
    end_ms: int
    speaker_id: str
    confidence: float


@dataclass
class _Centroid:
    speaker_id: str
    vector: np.ndarray
    count: int


@dataclass
class _SessionCluster:
    cursor_ms: int = 0
    next_index: int = 1
    centroids: list[_Centroid] | None = None
    spans: list[_Span] | None = None
    # Active utterance being built
    utt_start_ms: int | None = None
    utt_end_ms: int | None = None
    utt_features: list[np.ndarray] | None = None
    silence_ms: int = 0

    def __post_init__(self) -> None:
        if self.centroids is None:
            self.centroids = []
        if self.spans is None:
            self.spans = []
        if self.utt_features is None:
            self.utt_features = []


class OnlineSpeakerCluster:
    """Energie-VAD + spectrale embeddings + nearest-centroid clustering."""

    def start_session(self, session_id: str) -> None:
        self._sessions[session_id] = _SessionCluster()

    def stop_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionCluster] = {}

    def observe_pcm(
        self,
        session_id: str,
        pcm_f32: bytes,
        start_ms: int,
        end_ms: int,
        sample_rate: int,
    ) -> None:
        state = self._sessions.get(session_id)
        if state is None or sample_rate <= 0 or end_ms <= start_ms:
            return
        samples = np.frombuffer(pcm_f32, dtype="<f4")
        if samples.size == 0:
            return

        # Skip overlap already ingested (capture windows overlap).
        if end_ms <= state.cursor_ms:
            return
        if start_ms < state.cursor_ms:
            skip = state.cursor_ms - start_ms
            offset = int(round(skip * sample_rate / 1000))
            samples = samples[offset:]
            start_ms = state.cursor_ms
            if samples.size == 0 or end_ms <= start_ms:
                return

        frame = max(1, int(sample_rate * _FRAME_MS / 1000))
        hop = max(1, int(sample_rate * _HOP_MS / 1000))
        for i in range(0, max(0, samples.size - frame + 1), hop):
            window = samples[i : i + frame]
            abs_ms = start_ms + int(round(i * 1000 / sample_rate))
            energy = float(np.mean(window * window))
            if energy >= _ENERGY_FLOOR:
                feat = _spectral_embedding(window)
                if state.utt_start_ms is None:
                    state.utt_start_ms = abs_ms
                    state.utt_features = []
                state.utt_end_ms = abs_ms + _FRAME_MS
                state.utt_features.append(feat)
                state.silence_ms = 0
            else:
                if state.utt_start_ms is not None:
                    state.silence_ms += _HOP_MS
                    if state.silence_ms >= _SILENCE_END_MS:
                        self._flush_utterance(state)

        state.cursor_ms = end_ms

    def assign(
        self, session_id: str, start_ms: int | None, end_ms: int | None
    ) -> ClusterHit | None:
        state = self._sessions.get(session_id)
        if state is None or start_ms is None or end_ms is None or end_ms <= start_ms:
            return None
        # Flush trailing speech so recent finals can resolve.
        self._flush_utterance(state)
        best: _Span | None = None
        best_overlap = 0
        for span in state.spans or []:
            overlap = min(end_ms, span.end_ms) - max(start_ms, span.start_ms)
            if overlap > best_overlap:
                best_overlap = overlap
                best = span
        if best is None or best_overlap <= 0:
            return None
        return ClusterHit(speaker_id=best.speaker_id, confidence=best.confidence)

    def _flush_utterance(self, state: _SessionCluster) -> None:
        if (
            state.utt_start_ms is None
            or state.utt_end_ms is None
            or not state.utt_features
            or (state.utt_end_ms - state.utt_start_ms) < _MIN_SPEECH_MS
        ):
            state.utt_start_ms = None
            state.utt_end_ms = None
            state.utt_features = []
            state.silence_ms = 0
            return

        emb = np.mean(np.stack(state.utt_features, axis=0), axis=0)
        emb = _l2_normalize(emb)
        speaker_id, confidence = self._assign_centroid(state, emb)
        assert state.spans is not None
        state.spans.append(
            _Span(
                start_ms=state.utt_start_ms,
                end_ms=state.utt_end_ms,
                speaker_id=speaker_id,
                confidence=confidence,
            )
        )
        state.utt_start_ms = None
        state.utt_end_ms = None
        state.utt_features = []
        state.silence_ms = 0

    def _assign_centroid(self, state: _SessionCluster, emb: np.ndarray) -> tuple[str, float]:
        assert state.centroids is not None
        best_i = -1
        best_sim = -1.0
        for i, centroid in enumerate(state.centroids):
            sim = float(np.dot(emb, centroid.vector))
            if sim > best_sim:
                best_sim = sim
                best_i = i
        if best_i >= 0 and best_sim >= _NEW_SPEAKER_THRESHOLD:
            centroid = state.centroids[best_i]
            n = centroid.count + 1
            mixed = _l2_normalize((centroid.vector * centroid.count + emb) / n)
            state.centroids[best_i] = _Centroid(centroid.speaker_id, mixed, n)
            return centroid.speaker_id, max(0.0, min(1.0, best_sim))

        speaker_id = f"spk_{state.next_index}"
        state.next_index += 1
        state.centroids.append(_Centroid(speaker_id, emb, 1))
        return speaker_id, 0.55


def _spectral_embedding(frame: np.ndarray) -> np.ndarray:
    """Compact log-magnitude band energies (no extra ML deps)."""

    windowed = frame * np.hanning(frame.size)
    spectrum = np.abs(np.fft.rfft(windowed)) + 1e-8
    # Geometric band grouping across the spectrum.
    edges = np.geomspace(1, max(2, spectrum.size - 1), _N_BANDS + 1).astype(int)
    bands = np.zeros(_N_BANDS, dtype=np.float64)
    for i in range(_N_BANDS):
        lo, hi = edges[i], max(edges[i] + 1, edges[i + 1])
        bands[i] = np.log(float(np.mean(spectrum[lo:hi])))
    return _l2_normalize(bands)


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return np.zeros_like(vector)
    return vector / norm
