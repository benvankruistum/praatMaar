"""Hybride transcriptie-voortgang: tijdschatting + segment-floor.

Zie `docs/superpowers/specs/2026-08-10-hybrid-transcription-progress-design.md`.
"""

from __future__ import annotations

import math
import threading
import time

from indicator import set_transcription_progress

# Verwachte Whisper-duur ≈ vaste aanloop + RTF × audio-seconden.
# De aanloop dekt VAD/opstart; zonder die term zit een korte opname meteen
# tegen het plafond en lijkt de balk te bevriezen.
DEFAULT_RTF = 0.4
DEFAULT_OVERHEAD_S = 2.0
# Lineair tot hier op het geschatte eindtijdstip. Daarna kruipt de balk
# naar MAX_TICK_PERCENT; 100% zet alleen ``stop(100)`` als Whisper klaar is.
_LINEAR_PERCENT = 90
MAX_TICK_PERCENT = 99
_DEFAULT_INTERVAL_S = 0.1


def time_based_percent(
    elapsed_seconds: float,
    audio_seconds: float,
    *,
    rtf: float = DEFAULT_RTF,
    overhead_seconds: float = DEFAULT_OVERHEAD_S,
) -> int:
    """Voortgang 1–99 op basis van verstreken tijd vs verwachte Whisper-duur.

    Tot de schatting loopt de balk lineair naar 90%. Loopt Whisper langer,
    dan kruipt hij door naar 99% in plaats van stil te blijven staan op 95%.
    """

    if rtf < 0 or overhead_seconds < 0:
        return 1
    expected = float(overhead_seconds) + max(0.0, float(audio_seconds)) * float(rtf)
    if expected <= 0:
        return 1
    elapsed = max(0.0, float(elapsed_seconds))
    if elapsed <= expected:
        raw = int(_LINEAR_PERCENT * elapsed / expected)
        return max(1, min(_LINEAR_PERCENT, raw))
    over = elapsed - expected
    horizon = max(4.0, expected)
    crept = _LINEAR_PERCENT + (MAX_TICK_PERCENT - _LINEAR_PERCENT) * (
        1.0 - math.exp(-over / horizon)
    )
    return min(MAX_TICK_PERCENT, max(_LINEAR_PERCENT, round(crept)))


def hybrid_percent(time_percent: int, segment_percent: int | None) -> int:
    """Getoonde % = max(tijd, segment); segment None → alleen tijd."""

    t = max(0, min(100, int(time_percent)))
    if segment_percent is None:
        return t
    return max(t, max(0, min(100, int(segment_percent))))


class TranscriptionProgressTicker:
    """Daemon-ticker die tijdens Whisper `set_transcription_progress` bijwerkt."""

    def __init__(
        self,
        audio_seconds: float,
        *,
        rtf: float = DEFAULT_RTF,
        overhead_seconds: float = DEFAULT_OVERHEAD_S,
        interval_seconds: float = _DEFAULT_INTERVAL_S,
    ) -> None:
        self._audio_seconds = float(audio_seconds)
        self._rtf = float(rtf)
        self._overhead = float(overhead_seconds)
        self._interval = max(0.02, float(interval_seconds))
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._segment_floor: int | None = None
        self._started_at: float | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._started_at = time.perf_counter()
        self._stop.clear()
        # Eerste tick meteen zodat de pill niet op None/0 blijft hangen.
        self._publish()
        self._thread = threading.Thread(
            target=self._loop,
            name="transcription-progress-ticker",
            daemon=True,
        )
        self._thread.start()

    def note_segment(self, percent: int) -> None:
        with self._lock:
            floor = max(0, min(99, int(percent)))
            if self._segment_floor is None or floor > self._segment_floor:
                self._segment_floor = floor
        self._publish()

    def stop(self, final: int | None = 100) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None
        if final is None:
            set_transcription_progress(None)
        else:
            set_transcription_progress(final)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self._publish()

    def _publish(self) -> None:
        started = self._started_at
        if started is None:
            return
        elapsed = time.perf_counter() - started
        time_pct = time_based_percent(
            elapsed,
            self._audio_seconds,
            rtf=self._rtf,
            overhead_seconds=self._overhead,
        )
        with self._lock:
            segment = self._segment_floor
        set_transcription_progress(hybrid_percent(time_pct, segment))
