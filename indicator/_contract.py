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
WINDOW_ALPHA = 0.94
MARGIN_FRACTION = 0.10
POLL_INTERVAL_MS = 50
CANCELLED_DURATION_MS = 2000
ERROR_DURATION_MS = 4000
NUM_BARS = 18
WAVEFORM_GAIN = 9.0

# Pill-positiemodi (opgeslagen in config.json).
POSITION_TOP = "boven-midden"
POSITION_BOTTOM = "onder-midden"
POSITION_LAST = "laatst-geplaatst"
POSITION_PRESETS = frozenset({POSITION_TOP, POSITION_BOTTOM, POSITION_LAST})


def normalize_indicator_position(value: object, default: str = POSITION_TOP) -> str:
    text = str(value or "").strip()
    if text in POSITION_PRESETS:
        return text
    return default if default in POSITION_PRESETS else POSITION_TOP


def sanitize_indicator_xy(raw: object) -> tuple[int, int] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    try:
        return int(raw[0]), int(raw[1])
    except (TypeError, ValueError):
        return None


def clamp_indicator_xy(
    x: int,
    y: int,
    screen_w: int,
    screen_h: int,
    *,
    width: int = INDICATOR_WIDTH,
    height: int = INDICATOR_HEIGHT,
) -> tuple[int, int]:
    """Houdt de pill binnen het scherm (top-left herkomst, Y naar beneden)."""

    max_x = max(0, int(screen_w) - int(width))
    max_y = max(0, int(screen_h) - int(height))
    return max(0, min(int(x), max_x)), max(0, min(int(y), max_y))


def preset_indicator_xy(
    position: str,
    screen_w: int,
    screen_h: int,
    *,
    width: int = INDICATOR_WIDTH,
    height: int = INDICATOR_HEIGHT,
    margin_fraction: float = MARGIN_FRACTION,
) -> tuple[int, int]:
    """Top-/onder-midden in top-left schermcoördinaten."""

    x = (int(screen_w) - int(width)) // 2
    margin = int(int(screen_h) * margin_fraction)
    if position == POSITION_BOTTOM:
        y = int(screen_h) - int(height) - margin
    else:
        y = margin
    return clamp_indicator_xy(x, y, screen_w, screen_h, width=width, height=height)


# Max. tekens voor sticky bestemmingsnaam in de pill (voorkomt knippen).
MAX_DESTINATION_DISPLAY_CHARS = 24

# Kleuren uit canvas #2a (donkere HUD). Vorm draagt betekenis, kleur versterkt.
PILL_BG = "#1C1F23"
PILL_BG_ERROR = "#221819"  # rood-getinte capsule bij fout
TEXT_COLOR = "#F1F3F4"
MUTED_COLOR = "#A7AEB6"  # secundair op donker
SUBTLE_COLOR = "#8B929B"  # sublabel / dismiss-glyph
TAG_TEXT_COLOR = "#C9CFD6"  # modus-tag tekst
COLOR_RECORDING = "#FF5C57"
COLOR_TRANSCRIBING = "#FFB020"
COLOR_CANCELLED = "#8B929B"
COLOR_ERROR = "#FF6B6B"
COLOR_ERROR_LABEL = "#FF8F8B"
COLOR_MEETING_TAG = "#0F6CBD"
COLOR_MEETING_DOT = "#7FB1E0"  # meeting-tag stip op donker
COLOR_MEETING_TEXT = "#BFD8EF"  # meeting-tag tekst op donker

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


def transcribing_label(percent: int | None) -> str:
    """Label voor TRANSCRIBING; met percent → 'Transcriberen 45%'."""

    import i18n

    if percent is None:
        return i18n.t("state.transcribing")
    return i18n.t("state.transcribing_progress", percent=int(percent))


def transcription_percent(position_seconds: float, duration_seconds: float) -> int:
    """Voortgang 0–99 tijdens segment-iteratie (100% pas bij afronden)."""

    if duration_seconds <= 0:
        return 0
    return min(99, max(0, int(100.0 * float(position_seconds) / float(duration_seconds))))


def mode_tag(mode: str) -> str:
    """Modus-tag voor de pill (●/↔ + vertaalde korte naam)."""

    import i18n

    if mode == "meeting":
        return f"● {i18n.t('state.tag.meeting')}"
    if mode == "ptt":
        return f"● {i18n.t('state.tag.ptt')}"
    return f"↔ {i18n.t('state.tag.toggle')}"


def destination_display_name(name: str | None) -> str:
    """Kort een bestemmingsnaam in zodat die in de pill past."""

    if not name:
        return ""
    cleaned = name.strip()
    limit = MAX_DESTINATION_DISPLAY_CHARS
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


class DestinationPillModel:
    """
    Zichtbaarheid van de sticky-bestemmingspill (geen GUI).

    × verbergt de pill; sticky naam blijft. Weer tonen na nieuwe opname of
    bestemmingswissel (ook opnieuw dezelfde actief zetten).
    """

    def __init__(self) -> None:
        self.name: str | None = None
        self._dismissed = False

    @property
    def idle_visible(self) -> bool:
        return bool(self.name) and not self._dismissed

    def set_destination(self, name: str | None) -> None:
        self.name = name
        self._dismissed = False

    def dismiss(self) -> None:
        if self.name:
            self._dismissed = True

    def on_recording_started(self) -> None:
        self._dismissed = False


# =========================================================
# STATUSDOORGIFTE (thread-safe, producent -> GUI)
# =========================================================

_status_queue: queue.Queue[tuple[RecordingState, str]] = queue.Queue()
_level_lock = threading.Lock()
_levels: deque[float] = deque(maxlen=NUM_BARS)
_mic_levels: deque[float] = deque(maxlen=NUM_BARS)
_loopback_levels: deque[float] = deque(maxlen=NUM_BARS)
_progress_lock = threading.Lock()
_transcription_progress: int | None = None


def notify_state(state: RecordingState, mode: str = "toggle") -> None:
    """
    Meldt een nieuwe toestand aan de indicator. Veilig vanaf elke thread.

    `mode` is "toggle" of "ptt"; de indicator toont het als modus-tag.
    """

    if state != RecordingState.TRANSCRIBING:
        set_transcription_progress(None)
    _status_queue.put((state, mode))


def push_level(rms: float) -> None:
    """Schrijft een RMS-niveau in de waveform-buffer. Veilig vanaf de audiothread."""

    with _level_lock:
        _levels.append(float(rms))


def push_mic_level(rms: float) -> None:
    """RMS van de microfoonbron (vóór mix). Veilig vanaf de audiothread."""

    with _level_lock:
        _mic_levels.append(float(rms))


def push_loopback_level(rms: float) -> None:
    """RMS van WASAPI-loopback (vóór mix). Veilig vanaf de audiothread."""

    with _level_lock:
        _loopback_levels.append(float(rms))


def reset_levels() -> None:
    """Leegt de waveform-buffer (bij de start van een nieuwe opname)."""

    with _level_lock:
        _levels.clear()


def reset_source_levels() -> None:
    """Leegt mic- en loopback-waveform buffers (Meeting Buddy dual meters)."""

    with _level_lock:
        _mic_levels.clear()
        _loopback_levels.clear()


def set_transcription_progress(percent: int | None) -> None:
    """Zet voortgang 0–100 tijdens TRANSCRIBING, of None om te wissen."""

    global _transcription_progress
    with _progress_lock:
        if percent is None:
            _transcription_progress = None
        else:
            _transcription_progress = max(0, min(100, int(percent)))


def get_transcription_progress() -> int | None:
    with _progress_lock:
        return _transcription_progress


def snapshot_levels() -> list[float]:
    with _level_lock:
        return list(_levels)


def snapshot_mic_levels() -> list[float]:
    with _level_lock:
        return list(_mic_levels)


def snapshot_loopback_levels() -> list[float]:
    with _level_lock:
        return list(_loopback_levels)


def drain_status_queue() -> list[tuple[RecordingState, str]]:
    """Leegt de status-queue (aanroepen vanaf de GUI-/poll-thread)."""

    items: list[tuple[RecordingState, str]] = []
    try:
        while True:
            items.append(_status_queue.get_nowait())
    except queue.Empty:
        pass
    return items
