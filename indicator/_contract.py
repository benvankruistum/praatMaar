"""
Gedeeld contract voor de opname-indicator.

Toestanden, queues en uiterlijk-constanten — geen GUI, geen OS-API.
`opnamesessie` en tests importeren hier (via `indicator`) zonder Win32/AppKit.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from enum import Enum, auto
from typing import Literal


class RecordingState(Enum):
    """De fasen van de dicteercyclus."""

    IDLE = auto()
    PREPARING = auto()
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
# Statische states (Idle/Geannuleerd/Mislukt) animeren niets. De timer kan niet
# volledig stoppen — hij drenkt óók de statuswachtrij waarmee worker-threads een
# nieuwe state doorgeven — maar hij mag wél veel trager pollen en niet
# herschilderen. Zie tests/test_indicator_idle_cpu.py.
POLL_INTERVAL_IDLE_MS = 250
CANCELLED_DURATION_MS = 2000
ERROR_DURATION_MS = 4000
READY_CUE_DURATION_MS = 4000
NUM_BARS = 18
WAVEFORM_GAIN = 9.0
# Canvas 1a: 18 staven, 3 px breed, tot 24 px hoog (radius 2).
WAVEFORM_BAR_WIDTH = 3.0
WAVEFORM_BAR_MAX_HEIGHT = 24.0
# Canvas 04/10: de stopknop is een gevulde knop van 36×36; dismiss blijft 32.
STOP_BUTTON_SIZE = 36

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

# Kleuren uit canvas 1a (donkere HUD). Vorm draagt betekenis, kleur versterkt.
#
# Eén regel bepaalt het schema: **rood betekent uitsluitend "er wordt
# opgenomen"**. Daarom is transcriberen blauw en mislukt amber. Zie
# docs/design/pill.md; getest in tests/test_indicator_color_semantics.py.
#
# De gebruiker is kleurenblind: elke state moet óók zonder kleur te
# onderscheiden zijn. STATE_GLYPHS legt die vorm-per-state vast.
PILL_BG = "#202328"
PILL_BG_ERROR = "#221E18"  # amber-getinte capsule bij fout
TEXT_COLOR = "#E6E8EB"
MUTED_COLOR = "#A7AEB6"  # secundair op donker
SUBTLE_COLOR = "#8A929C"  # sublabel / dismiss-glyph (canvas text-2)
TAG_TEXT_COLOR = "#C9CFD6"  # modus-tag tekst
COLOR_RECORDING = "#E5484D"  # rec — alleen tijdens opnemen
COLOR_RECORDING_DOT = "#F0575C"  # iets feller voor de pulsdot
COLOR_TRANSCRIBING = "#6E9BFF"  # work — verwerken
COLOR_TRANSCRIBING_TEXT = "#9EC0FF"  # percentage/label op donker
COLOR_PREPARING = "#8A929C"  # neutraal grijs: nog geen audio
COLOR_CANCELLED = "#8B929B"
COLOR_OK = "#3DD68C"  # ready-cue
COLOR_ERROR = "#F5A524"  # warn — mislukt (amber, niet rood)
COLOR_ERROR_LABEL = "#F5C063"
COLOR_MEETING_TAG = "#0F6CBD"
COLOR_MEETING_DOT = "#7FB1E0"  # meeting-tag stip op donker
COLOR_MEETING_TEXT = "#BFD8EF"  # meeting-tag tekst op donker
# Chunk-pipeline LED’s (LCD-stijl op de opname-pill).
COLOR_CHUNK_LED_IDLE = MUTED_COLOR
COLOR_CHUNK_LED_VAD = COLOR_MEETING_DOT
COLOR_CHUNK_LED_FIXED = COLOR_TRANSCRIBING
CHUNK_LED_HIT_SECONDS = 0.8

STATE_LABEL_KEYS = {
    RecordingState.PREPARING: "state.preparing",
    RecordingState.RECORDING: "state.recording",
    RecordingState.TRANSCRIBING: "state.transcribing",
    RecordingState.CANCELLED: "state.cancelled",
    RecordingState.ERROR: "state.error",
}

STATE_COLORS = {
    RecordingState.PREPARING: COLOR_PREPARING,
    RecordingState.RECORDING: COLOR_RECORDING,
    RecordingState.TRANSCRIBING: COLOR_TRANSCRIBING,
    RecordingState.CANCELLED: COLOR_CANCELLED,
    RecordingState.ERROR: COLOR_ERROR,
}

# Vorm per state — de betekenisdrager die niet van kleur afhangt. Wie geen
# kleurverschil ziet, herkent de state aan dít silhouet. Wijzig alleen samen
# met de bijbehorende _paint_*-routine in indicator/_qt.py.
GLYPH_PULSE_DOT = "pulse-dot"  # opname: kloppende stip + waveform
GLYPH_SOFT_DOT = "soft-dot"  # voorbereiden: trage stip + marching dots
GLYPH_ARC = "arc"  # transcriberen: draaiende arc + voortgang
GLYPH_CIRCLE_SLASH = "circle-slash"  # geannuleerd: doorgestreepte cirkel
GLYPH_TRIANGLE = "triangle"  # mislukt: waarschuwingsdriehoek + actieknop

STATE_GLYPHS = {
    RecordingState.PREPARING: GLYPH_SOFT_DOT,
    RecordingState.RECORDING: GLYPH_PULSE_DOT,
    RecordingState.TRANSCRIBING: GLYPH_ARC,
    RecordingState.CANCELLED: GLYPH_CIRCLE_SLASH,
    RecordingState.ERROR: GLYPH_TRIANGLE,
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


def elapsed_label(seconds: float) -> str:
    """Looptijd voor de opname-pill: ``mm:ss``, met uren zodra die er zijn.

    Tabular-nums in de paint zorgt dat er niets verspringt terwijl de teller
    loopt (canvas 1a, type-sectie).
    """

    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


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

# Queue-item: (state, mode, hint). Lege hint = geen hint-tekst.
_status_queue: queue.Queue[tuple[RecordingState, str, str]] = queue.Queue()
_level_lock = threading.Lock()
_levels: deque[float] = deque(maxlen=NUM_BARS)
_mic_levels: deque[float] = deque(maxlen=NUM_BARS)
_loopback_levels: deque[float] = deque(maxlen=NUM_BARS)
_progress_lock = threading.Lock()
_transcription_progress: int | None = None
_chunk_led_lock = threading.Lock()
_chunk_leds_enabled = False
_chunk_vad_until = 0.0
_chunk_fixed_until = 0.0


def set_chunk_leds_enabled(enabled: bool) -> None:
    """Toon of verberg de chunk-trigger-LED’s op de opname-pill."""

    global _chunk_leds_enabled, _chunk_vad_until, _chunk_fixed_until
    with _chunk_led_lock:
        _chunk_leds_enabled = bool(enabled)
        if not _chunk_leds_enabled:
            _chunk_vad_until = 0.0
            _chunk_fixed_until = 0.0


def signal_chunk_trigger(reason: Literal["vad", "fixed"] | str) -> None:
    """Laat de bijbehorende LED kort oplichten (VAD of tijdvenster)."""

    global _chunk_vad_until, _chunk_fixed_until
    until = time.monotonic() + CHUNK_LED_HIT_SECONDS
    with _chunk_led_lock:
        if not _chunk_leds_enabled:
            return
        if reason == "vad":
            _chunk_vad_until = until
        elif reason == "fixed":
            _chunk_fixed_until = until


def chunk_led_snapshot() -> tuple[bool, bool, bool]:
    """(enabled, vad_lit, fixed_lit) — veilig vanaf de GUI-pollthread."""

    now = time.monotonic()
    with _chunk_led_lock:
        return (
            _chunk_leds_enabled,
            _chunk_vad_until > now,
            _chunk_fixed_until > now,
        )


def notify_state(
    state: RecordingState,
    mode: str = "toggle",
    *,
    hint: str | None = None,
) -> None:
    """
    Meldt een nieuwe toestand aan de indicator. Veilig vanaf elke thread.

    `mode` is "toggle" of "ptt"; de indicator toont het als modus-tag.
    `hint` is al-vertaalde korte tekst (bijv. bij ERROR/PREPARING). Lege string
    of None = geen hint. Bij IDLE en bij elke niet-ERROR/niet-PREPARING-toestand
    wordt de hint automatisch gewist zodat callers niet hoeven te onthouden.
    """

    if state != RecordingState.TRANSCRIBING:
        set_transcription_progress(None)
    if state in (RecordingState.ERROR, RecordingState.PREPARING):
        hint_str = "" if hint is None else str(hint)
    else:
        hint_str = ""
    _status_queue.put((state, mode, hint_str))


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


def drain_status_queue() -> list[tuple[RecordingState, str, str]]:
    """Leegt de status-queue (aanroepen vanaf de GUI-/poll-thread).

    Elk item is ``(state, mode, hint)``; ``hint`` is ``""`` als er geen hint is.
    """

    items: list[tuple[RecordingState, str, str]] = []
    try:
        while True:
            items.append(_status_queue.get_nowait())
    except queue.Empty:
        pass
    return items
