"""
Opname-indicator voor praatMaar.

Gedeeld contract (`RecordingState`, notify/push/reset) plus de Qt status-pill.
`RecordingIndicator` wordt lazy geïmporteerd zodat contracttests geen QApplication
hoeven te maken.
"""

from __future__ import annotations

from typing import Any

from ._contract import (
    RecordingState,
    notify_state,
    push_level,
    push_loopback_level,
    push_mic_level,
    reset_levels,
    reset_source_levels,
    set_transcription_progress,
)

__all__ = [
    "RecordingState",
    "RecordingIndicator",
    "notify_state",
    "push_level",
    "push_mic_level",
    "push_loopback_level",
    "reset_levels",
    "reset_source_levels",
    "set_transcription_progress",
]


def _select_indicator() -> Any:
    from ._qt import RecordingIndicator

    return RecordingIndicator


def __getattr__(name: str) -> Any:
    if name == "RecordingIndicator":
        return _select_indicator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
