"""Fase-tijden van één dicteercyclus (na stop), voor praatMaar.log."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from indicator import RecordingState


class Host(Protocol):
    def paste(self) -> None: ...


NotifyFn = Callable[[RecordingState], None] | Callable[[RecordingState, str | None], None]


@dataclass
class CycleTiming:
    """Fase-tijden van één dicteercyclus (na stop), voor `praatMaar.log`."""

    session_id: str
    path: str  # "full" | "chunk" | "partial"
    record_s: float
    stop_at: float
    stop_join_s: float
    wav_s: float | None = None
    whisper_s: float | None = None
    deliver_s: float | None = None

    def log(self) -> None:
        print(format_cycle_timing(self))


def format_cycle_timing(timing: CycleTiming) -> str:
    """Machine-leesbare timingregel; zie `docs/profiling.md`."""

    sid = (timing.session_id or "?")[:8]

    def _fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.3f}s"

    total = max(0.0, time.perf_counter() - timing.stop_at)
    return (
        f"cycle.timing id={sid} path={timing.path} "
        f"record={timing.record_s:.3f}s stop_join={timing.stop_join_s:.3f}s "
        f"wav={_fmt(timing.wav_s)} whisper={_fmt(timing.whisper_s)} "
        f"deliver={_fmt(timing.deliver_s)} total_after_stop={total:.3f}s"
    )
