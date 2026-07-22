"""
Opname-indicator voor praatMaar.

Gedeeld contract (`RecordingState`, notify/push/reset) plus per-OS
vensterimplementatie:

- Windows: tkinter + ``WS_EX_NOACTIVATE`` (`_win`)
- macOS: native ``NSPanel`` / nonactivatingPanel (`_mac`, ADR-0002)

`RecordingIndicator` wordt lazy gekozen op ``sys.platform``, zodat tests
`RecordingState` kunnen importeren zonder GUI-toolkits.
"""

from __future__ import annotations

import sys
from typing import Any

from ._contract import (
    RecordingState,
    notify_state,
    push_level,
    reset_levels,
    set_transcription_progress,
)

__all__ = [
    "RecordingState",
    "RecordingIndicator",
    "notify_state",
    "push_level",
    "reset_levels",
    "set_transcription_progress",
]


def _select_indicator() -> Any:
    if sys.platform == "win32":
        from ._win import RecordingIndicator

        return RecordingIndicator

    if sys.platform == "darwin":
        from ._mac import RecordingIndicator

        return RecordingIndicator

    raise RuntimeError(
        f"Geen indicator voor platform {sys.platform!r} (ondersteund: win32, darwin)."
    )


def __getattr__(name: str) -> Any:
    if name == "RecordingIndicator":
        return _select_indicator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
