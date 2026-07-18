"""
Opname-indicator voor praatMaar.

Een kleine, altijd-zichtbare status-pill die de dicteercyclus toont
(opname / transcriberen / geannuleerd / fout) zonder de focus te stelen van
het actieve invoerveld. Zie de spec onder
`.scratch/opname-indicator/spec.md`.

Techniek: tkinter (stdlib) + een ctypes-shim die WS_EX_NOACTIVATE op de HWND
zet, zodat het venster nooit de voorgrond pakt. Geen extra dependencies.
"""

from __future__ import annotations

import ctypes
import math
import queue
import sys
import threading
from collections import deque
from ctypes import wintypes
from enum import Enum, auto
from typing import Any


# =========================================================
# TOESTANDEN
# =========================================================

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

# Maatvoering. De POC (260x46) voelde te klein; ~1,3x groter voor zichtbaarheid.
INDICATOR_WIDTH = 340
INDICATOR_HEIGHT = 60

# Doorschijnendheid van het hele venster (1.0 = ondoorzichtig).
WINDOW_ALPHA = 0.92

# Afgeronde hoeken via een transparante kleur-key. Op sommige Windows-setups
# maakt dit het hele venster doorzichtig i.p.v. alleen de hoeken; dan uitzetten
# voor een (nagenoeg) rechthoekige, doorschijnende pill.
USE_TRANSPARENT_KEY = True

# Kleur-key die volledig transparant wordt gemaakt (alleen als bovenstaande aan).
# Mag door geen enkel getekend element gebruikt worden.
TRANSPARENT_KEY = "#ff00fe"

# Afstand tot de schermrand als fractie van de schermhoogte (ruime marge,
# zodat de pill nooit tegen menubalk of taakbalk plakt).
MARGIN_FRACTION = 0.10

# Poll-tempo van de GUI (ms). ~50 ms = ~20 fps, genoeg voor de waveform.
POLL_INTERVAL_MS = 50

# Hoe lang de transient-toestanden zichtbaar blijven voordat de pill verdwijnt.
CANCELLED_DURATION_MS = 2000
ERROR_DURATION_MS = 4000

# Waveform.
NUM_BARS = 18
WAVEFORM_GAIN = 9.0  # RMS van spraak is klein; opschalen naar 0..1.

# Lettertype.
LABEL_FONT = ("Segoe UI", 13)
TAG_FONT = ("Segoe UI", 9)

# Kleuren.
PILL_BG = "#202124"
TEXT_COLOR = "#f1f3f4"
MUTED_COLOR = "#9aa0a6"
COLOR_RECORDING = "#ff4d4d"
COLOR_TRANSCRIBING = "#ffb020"
COLOR_CANCELLED = "#9aa0a6"
COLOR_ERROR = "#ff5252"

# Labels per toestand — via i18n (zie state_label()).
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


# =========================================================
# STATUSDOORGIFTE (thread-safe, producent -> GUI)
# =========================================================

# Event-driven status: producenten (dictation.py) leggen berichten neer,
# de GUI leegt de queue op z'n after-tick.
_status_queue: "queue.Queue[tuple[RecordingState, str]]" = queue.Queue()

# Waveform: hoogfrequente "laatste waarden tellen"-data, los van de status.
_level_lock = threading.Lock()
_levels: deque[float] = deque(maxlen=NUM_BARS)


def notify_state(state: RecordingState, mode: str = "toggle") -> None:
    """
    Meldt een nieuwe toestand aan de indicator. Veilig vanaf elke thread.

    `mode` is "toggle" (nu) of "ptt" (later push-to-talk); de indicator toont
    het als modus-tag.
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


def _snapshot_levels() -> list[float]:
    with _level_lock:
        return list(_levels)


# =========================================================
# WINDOWS API (ctypes) — no-activate-shim
# =========================================================

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def _configure_user32() -> Any:
    """Haalt user32 op en zet de argtypes goed (belangrijk op 64-bit)."""

    user32 = ctypes.windll.user32

    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.LONG,
    ]

    user32.ShowWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    return user32


# =========================================================
# INDICATOR
# =========================================================

class RecordingIndicator:
    """
    Het tkinter-venster met de status-pill.

    Draait op de hoofdthread (Tk-eis). `run()` blokkeert met de mainloop;
    `request_stop()` laat 'm netjes eindigen (bijv. vanuit een signaal-handler).
    """

    def __init__(self, position: str = "boven-midden") -> None:
        if sys.platform != "win32":
            raise SystemExit(
                "De opname-indicator werkt alleen op Windows "
                "(vereist de WS_EX_NOACTIVATE-shim)."
            )

        # tkinter pas hier importeren: puur cosmetisch, houdt de module-top
        # vrij van GUI-imports bij een kale import.
        import tkinter as tk

        self._tk = tk
        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._frame = 0
        self._visible = False
        self._hide_after_id: str | None = None
        self._stop_requested = False
        self._position = position
        self._destination: str | None = None

        # Wordt bij elke toestandswissel aangeroepen (op de hoofdthread); door
        # main() bedraad naar de tray zodat de pill de enige toestandseigenaar is.
        self.state_listener: "Any | None" = None

        # Thread-veilige marshalling: andere threads (bijv. de tray) leggen hier
        # een callable neer; de poll-tick voert het uit op de hoofdthread.
        self._main_calls: "queue.Queue[Any]" = queue.Queue()

        try:
            self._build_window(position)
        except Exception as exc:  # harde afhankelijkheid: falen = stoppen
            raise SystemExit(
                f"De opname-indicator kon niet worden geïnitialiseerd: {exc}"
            ) from exc

    # ----- opbouw (geverifieerde volgorde, spec §3) -----

    def _build_window(self, position: str) -> None:
        tk = self._tk

        # 1. Verborgen opbouwen.
        self.root = tk.Tk()
        self.root.withdraw()

        # 2. Vensterstijl: randloos, altijd bovenop, doorschijnend, evt. gevormd.
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", WINDOW_ALPHA)

        bg = TRANSPARENT_KEY if USE_TRANSPARENT_KEY else PILL_BG
        if USE_TRANSPARENT_KEY:
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.root.configure(bg=bg)

        self._place_window(position)

        self.canvas = tk.Canvas(
            self.root,
            width=INDICATOR_WIDTH,
            height=INDICATOR_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=bg,
        )
        self.canvas.pack()

        self._build_canvas_items()

        # 3. HWND realiseren terwijl verborgen.
        self.root.update_idletasks()
        self._hwnd = self.root.winfo_id()

        # 4. NU pas de ex-style stempelen — vóór het venster ooit getoond is.
        self._user32 = _configure_user32()
        ex_style = self._user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        self._user32.SetWindowLongW(
            self._hwnd,
            GWL_EXSTYLE,
            ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        )

        # 5. (Tonen gebeurt pas bij de eerste RECORDING, via _show_window.)

    def _place_window(self, position: str) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        x = (screen_w - INDICATOR_WIDTH) // 2
        margin = int(screen_h * MARGIN_FRACTION)

        if position == "onder-midden":
            y = screen_h - INDICATOR_HEIGHT - margin
        else:  # "boven-midden" (standaard)
            y = margin

        self.root.geometry(
            f"{INDICATOR_WIDTH}x{INDICATOR_HEIGHT}+{x}+{y}"
        )

    # ----- Canvas-items (eenmalig aanmaken; nooit delete/recreate) -----

    def _build_canvas_items(self) -> None:
        c = self.canvas
        h = INDICATOR_HEIGHT
        cy = h / 2

        # Capsule-achtergrond (afgeronde "pill").
        c.create_polygon(
            self._round_rect_points(1, 1, INDICATOR_WIDTH - 1, h - 1, (h - 2) / 2),
            smooth=True,
            fill=PILL_BG,
            outline="",
            tags=("capsule",),
        )

        # Statuspuntje links.
        self._dot_cx = 26
        self._dot_r = 7
        self._dot = c.create_oval(0, 0, 0, 0, fill=COLOR_RECORDING, outline="")

        # Label.
        self._label = c.create_text(
            44, cy, text="", anchor="w", fill=TEXT_COLOR, font=LABEL_FONT
        )

        # Waveform-balkjes (alleen zichtbaar bij opname).
        self._wf_x1 = 150
        self._wf_x2 = 252
        self._bars = []
        span = self._wf_x2 - self._wf_x1
        bar_slot = span / NUM_BARS
        bar_w = max(2, bar_slot * 0.55)
        for i in range(NUM_BARS):
            bx = self._wf_x1 + i * bar_slot
            bar = c.create_rectangle(
                bx, cy - 1, bx + bar_w, cy + 1,
                fill=COLOR_RECORDING, outline="", state="hidden",
            )
            self._bars.append(bar)

        # Drie "lopende" stippen (alleen bij transcriberen).
        self._mdots = []
        for i in range(3):
            mx = 190 + i * 18
            dot = c.create_oval(
                mx, cy - 4, mx + 8, cy + 4,
                fill=MUTED_COLOR, outline="", state="hidden",
            )
            self._mdots.append(dot)

        # Modus-tag rechts.
        self._tag = c.create_text(
            INDICATOR_WIDTH - 16, cy, text="", anchor="e",
            fill=MUTED_COLOR, font=TAG_FONT,
        )

    @staticmethod
    def _round_rect_points(
        x1: float, y1: float, x2: float, y2: float, r: float
    ) -> list[float]:
        """Punten voor een afgeronde rechthoek (smooth polygon)."""

        return [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]

    # ----- tonen / verbergen (altijd no-activate) -----

    def _show_window(self) -> None:
        if self._visible:
            return

        # Tk-native mappen: deiconify() past de geometrie toe en houdt het
        # venster gemapt (een rauwe ShowWindow wordt door Tk teruggedraaid).
        # De WS_EX_NOACTIVATE-shim staat al vast (uit _build_window), dus dit
        # tonen pakt de focus niet.
        self.root.deiconify()
        self.root.update_idletasks()
        self._user32.SetWindowPos(
            self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        self._visible = True

    def _hide_window(self) -> None:
        if not self._visible:
            return

        self.root.withdraw()
        self._visible = False

    # ----- statusverwerking -----

    def _cancel_hide_timer(self) -> None:
        if self._hide_after_id is not None:
            self.root.after_cancel(self._hide_after_id)
            self._hide_after_id = None

    def _apply_state(self, state: RecordingState, mode: str) -> None:
        self._mode = mode
        self._state = state
        self._notify_listener(state, mode)

        # Een nieuwe toestand annuleert een geplande verberg-actie.
        self._cancel_hide_timer()

        if state == RecordingState.IDLE:
            self._hide_window()
            return

        self._show_window()

        # Transient-toestanden plannen zelf hun terugval naar IDLE.
        if state == RecordingState.CANCELLED:
            self._hide_after_id = self.root.after(
                CANCELLED_DURATION_MS, self._transient_expired
            )
        elif state == RecordingState.ERROR:
            self._hide_after_id = self.root.after(
                ERROR_DURATION_MS, self._transient_expired
            )

    def _transient_expired(self) -> None:
        self._hide_after_id = None
        self._state = RecordingState.IDLE
        self._notify_listener(RecordingState.IDLE, self._mode)
        self._hide_window()

    def _notify_listener(self, state: RecordingState, mode: str) -> None:
        if self.state_listener is not None:
            try:
                self.state_listener(state, mode)
            except Exception:
                pass  # de listener mag de pill nooit laten crashen

    def call_on_main(self, fn: "Any") -> None:
        """Laat `fn` op de hoofdthread uitvoeren. Veilig vanaf elke thread."""

        self._main_calls.put(fn)

    def set_position(self, position: str) -> None:
        """Herpositioneert de pill live (aangeroepen op de hoofdthread)."""

        self._position = position
        self._place_window(position)

    def set_destination(self, name: str | None) -> None:
        """Onthoudt de actieve bestemming; idle-rendering volgt in Task 5."""

        self._destination = name

    # ----- de poll-tick (GUI-thread) -----

    def _tick(self) -> None:
        if self._stop_requested:
            self.root.quit()
            return

        # 1. Status-queue legen.
        try:
            while True:
                state, mode = _status_queue.get_nowait()
                self._apply_state(state, mode)
        except queue.Empty:
            pass

        # 1b. Gemarshalde calls van andere threads uitvoeren (bijv. tray → dialoog).
        try:
            while True:
                self._main_calls.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass

        # 2. Animatie + hertekenen.
        self._frame += 1
        if self._visible:
            self._render()

        # 3. Opnieuw inplannen.
        self.root.after(POLL_INTERVAL_MS, self._tick)

    def _render(self) -> None:
        c = self.canvas
        state = self._state
        cy = INDICATOR_HEIGHT / 2
        color = STATE_COLORS.get(state, MUTED_COLOR)

        # Label.
        c.itemconfigure(self._label, text=state_label(state))

        # Statuspuntje — pulserend bij opname, anders statisch.
        if state == RecordingState.RECORDING:
            pulse = 0.5 + 0.5 * math.sin(self._frame * 0.35)
            r = self._dot_r * (0.7 + 0.3 * pulse)
        else:
            r = self._dot_r
        c.coords(
            self._dot,
            self._dot_cx - r, cy - r, self._dot_cx + r, cy + r,
        )
        c.itemconfigure(self._dot, fill=color)

        # Waveform (alleen opname).
        recording = state == RecordingState.RECORDING
        self._render_waveform(recording, color, cy)

        # Lopende stippen (alleen transcriberen).
        self._render_marching_dots(state == RecordingState.TRANSCRIBING, cy)

        # Modus-tag (bij opname en transcriberen).
        if state in (RecordingState.RECORDING, RecordingState.TRANSCRIBING):
            import i18n

            # ↔ en ● renderen betrouwbaar in Segoe UI (⇄/◉ niet altijd).
            tag = (
                f"● {i18n.t('state.tag.ptt')}"
                if self._mode == "ptt"
                else f"↔ {i18n.t('state.tag.toggle')}"
            )
            c.itemconfigure(self._tag, text=tag, state="normal")
        else:
            c.itemconfigure(self._tag, text="", state="hidden")

    def _render_waveform(
        self, visible: bool, color: str, cy: float
    ) -> None:
        c = self.canvas

        if not visible:
            for bar in self._bars:
                c.itemconfigure(bar, state="hidden")
            return

        levels = _snapshot_levels()
        # Rechts uitlijnen: recente waarden aan de rechterkant.
        padded = [0.0] * (NUM_BARS - len(levels)) + levels

        span = self._wf_x2 - self._wf_x1
        bar_slot = span / NUM_BARS
        bar_w = max(2, bar_slot * 0.55)
        max_half = (INDICATOR_HEIGHT / 2) - 12

        for i, bar in enumerate(self._bars):
            level = min(1.0, padded[i] * WAVEFORM_GAIN)
            half = max(1.5, level * max_half)
            bx = self._wf_x1 + i * bar_slot
            c.coords(bar, bx, cy - half, bx + bar_w, cy + half)
            c.itemconfigure(bar, state="normal", fill=color)

    def _render_marching_dots(self, visible: bool, cy: float) -> None:
        c = self.canvas

        if not visible:
            for dot in self._mdots:
                c.itemconfigure(dot, state="hidden")
            return

        active = (self._frame // 4) % 3
        for i, dot in enumerate(self._mdots):
            fill = COLOR_TRANSCRIBING if i == active else MUTED_COLOR
            c.itemconfigure(dot, state="normal", fill=fill)

    # ----- levenscyclus -----

    def run(self) -> None:
        """Start de poll-tick en de blokkerende mainloop (hoofdthread)."""

        self.root.after(POLL_INTERVAL_MS, self._tick)
        self.root.mainloop()

    def request_stop(self) -> None:
        """Vraagt de mainloop netjes te stoppen (thread-/signaal-veilig)."""

        self._stop_requested = True

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
