"""
Gedeeld contract voor de opname-indicator.

Toestanden, queues en uiterlijk-constanten — geen GUI, geen OS-API.
`opnamesessie` en tests importeren hier (via `indicator`) zonder Win32/AppKit.
"""

from __future__ import annotations

import queue
import threading
from collections import deque
from enum import Enum, auto


class RecordingState(Enum):
    """De fasen van de dicteercyclus."""

    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    CANCELLED = auto()
    ERROR = auto()


# =========================================================
# UITERLIJK (constanten — bedoeld om te tunen)
# =========================================================

INDICATOR_WIDTH = 340
INDICATOR_HEIGHT = 60
WINDOW_ALPHA = 0.92
MARGIN_FRACTION = 0.10
POLL_INTERVAL_MS = 50
CANCELLED_DURATION_MS = 2000
ERROR_DURATION_MS = 4000
NUM_BARS = 18
WAVEFORM_GAIN = 9.0

PILL_BG = "#202124"
TEXT_COLOR = "#f1f3f4"
MUTED_COLOR = "#9aa0a6"
COLOR_RECORDING = "#ff4d4d"
COLOR_TRANSCRIBING = "#ffb020"
COLOR_CANCELLED = "#9aa0a6"
COLOR_ERROR = "#ff5252"

STATE_LABEL_KEYS = {
    RecordingState.RECORDING: "state.recording",
    RecordingState.TRANSCRIBING: "state.transcribing",
    RecordingState.CANCELLED: "state.cancelled",
    RecordingState.ERROR: "state.error",
}

STATE_COLORS = {
    RecordingState.RECORDING: COLOR_RECORDING,
    RecordingState.TRANSCRIBING: COLOR_TRANSCRIBING,
    RecordingState.CANCELLED: COLOR_CANCELLED,
    RecordingState.ERROR: COLOR_ERROR,
}


def state_label(state: RecordingState) -> str:
    import i18n

    key = STATE_LABEL_KEYS.get(state)
    return i18n.t(key) if key else ""


def mode_tag(mode: str) -> str:
    """Modus-tag voor de pill (●/↔ + vertaalde korte naam)."""

    import i18n

    if mode == "ptt":
        return f"● {i18n.t('state.tag.ptt')}"
    return f"↔ {i18n.t('state.tag.toggle')}"


# =========================================================
# STATUSDOORGIFTE (thread-safe, producent -> GUI)
# =========================================================

_status_queue: queue.Queue[tuple[RecordingState, str]] = queue.Queue()
_level_lock = threading.Lock()
_levels: deque[float] = deque(maxlen=NUM_BARS)


def notify_state(state: RecordingState, mode: str = "toggle") -> None:
    """
    Meldt een nieuwe toestand aan de indicator. Veilig vanaf elke thread.

    `mode` is "toggle" of "ptt"; de indicator toont het als modus-tag.
    """

    _status_queue.put((state, mode))


def push_level(rms: float) -> None:
    """Schrijft een RMS-niveau in de waveform-buffer. Veilig vanaf de audiothread."""

    with _level_lock:
        _levels.append(float(rms))


def reset_levels() -> None:
    """Leegt de waveform-buffer (bij de start van een nieuwe opname)."""

    with _level_lock:
        _levels.clear()


def snapshot_levels() -> list[float]:
    with _level_lock:
        return list(_levels)


def drain_status_queue() -> list[tuple[RecordingState, str]]:
    """Leegt de status-queue (aanroepen vanaf de GUI-/poll-thread)."""

    items: list[tuple[RecordingState, str]] = []
    try:
        while True:
            items.append(_status_queue.get_nowait())
    except queue.Empty:
        pass
    return items
