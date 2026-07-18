"""
Windows-indicator: tkinter + WS_EX_NOACTIVATE-shim.

Geen focus-diefstal van het actieve invoerveld. Zie ADR-0002 voor het
macOS-pad (`_mac.py`).
"""

from __future__ import annotations

import ctypes
import math
import queue
import sys
from ctypes import wintypes
from typing import Any

from ._contract import (
    CANCELLED_DURATION_MS,
    COLOR_RECORDING,
    COLOR_TRANSCRIBING,
    ERROR_DURATION_MS,
    INDICATOR_HEIGHT,
    INDICATOR_WIDTH,
    MARGIN_FRACTION,
    MUTED_COLOR,
    NUM_BARS,
    PILL_BG,
    POLL_INTERVAL_MS,
    STATE_COLORS,
    TEXT_COLOR,
    WAVEFORM_GAIN,
    WINDOW_ALPHA,
    RecordingState,
    drain_status_queue,
    mode_tag,
    snapshot_levels,
    state_label,
)

# Afgeronde hoeken via een transparante kleur-key. Op sommige Windows-setups
# maakt dit het hele venster doorzichtig i.p.v. alleen de hoeken.
USE_TRANSPARENT_KEY = True
TRANSPARENT_KEY = "#ff00fe"

LABEL_FONT = ("Segoe UI", 13)
TAG_FONT = ("Segoe UI", 9)

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


class RecordingIndicator:
    """
    Het tkinter-venster met de status-pill (Windows).

    Draait op de hoofdthread (Tk-eis). `run()` blokkeert met de mainloop;
    `request_stop()` laat 'm netjes eindigen.
    """

    def __init__(self, position: str = "boven-midden") -> None:
        if sys.platform != "win32":
            raise SystemExit(
                "De Windows-indicator werkt alleen op win32 "
                "(vereist de WS_EX_NOACTIVATE-shim)."
            )

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
        except Exception as exc:
            raise SystemExit(
                f"De opname-indicator kon niet worden geïnitialiseerd: {exc}"
            ) from exc

    def _build_window(self, position: str) -> None:
        tk = self._tk

        self.root = tk.Tk()
        self.root.withdraw()
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

        self.root.update_idletasks()
        self._hwnd = self.root.winfo_id()

        self._user32 = _configure_user32()
        ex_style = self._user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        self._user32.SetWindowLongW(
            self._hwnd,
            GWL_EXSTYLE,
            ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        )

    def _place_window(self, position: str) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        x = (screen_w - INDICATOR_WIDTH) // 2
        margin = int(screen_h * MARGIN_FRACTION)

        if position == "onder-midden":
            y = screen_h - INDICATOR_HEIGHT - margin
        else:
            y = margin

        self.root.geometry(
            f"{INDICATOR_WIDTH}x{INDICATOR_HEIGHT}+{x}+{y}"
        )

    def _build_canvas_items(self) -> None:
        c = self.canvas
        h = INDICATOR_HEIGHT
        cy = h / 2

        c.create_polygon(
            self._round_rect_points(1, 1, INDICATOR_WIDTH - 1, h - 1, (h - 2) / 2),
            smooth=True,
            fill=PILL_BG,
            outline="",
            tags=("capsule",),
        )

        self._dot_cx = 26
        self._dot_r = 7
        self._dot = c.create_oval(0, 0, 0, 0, fill=COLOR_RECORDING, outline="")

        self._label = c.create_text(
            44, cy, text="", anchor="w", fill=TEXT_COLOR, font=LABEL_FONT
        )

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

        self._mdots = []
        for i in range(3):
            mx = 190 + i * 18
            dot = c.create_oval(
                mx, cy - 4, mx + 8, cy + 4,
                fill=MUTED_COLOR, outline="", state="hidden",
            )
            self._mdots.append(dot)

        self._tag = c.create_text(
            INDICATOR_WIDTH - 16, cy, text="", anchor="e",
            fill=MUTED_COLOR, font=TAG_FONT,
        )

    @staticmethod
    def _round_rect_points(
        x1: float, y1: float, x2: float, y2: float, r: float
    ) -> list[float]:
        return [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]

    def _show_window(self) -> None:
        if self._visible:
            return

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

    def _apply_idle_visibility(self) -> None:
        """In idle: pill zichtbaar houden als er een sticky bestemming actief is."""

        if self._destination:
            self._show_window()
        else:
            self._hide_window()

    # ----- statusverwerking -----

    def _cancel_hide_timer(self) -> None:
        if self._hide_after_id is not None:
            self.root.after_cancel(self._hide_after_id)
            self._hide_after_id = None

    def _apply_state(self, state: RecordingState, mode: str) -> None:
        self._mode = mode
        self._state = state
        self._notify_listener(state, mode)
        self._cancel_hide_timer()

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
            if self._visible:
                self._render()
            return

        self._show_window()

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
        self._apply_idle_visibility()
        if self._visible:
            self._render()

    def _notify_listener(self, state: RecordingState, mode: str) -> None:
        if self.state_listener is not None:
            try:
                self.state_listener(state, mode)
            except Exception:
                pass

    def call_on_main(self, fn: Any) -> None:
        self._main_calls.put(fn)

    def set_position(self, position: str) -> None:
        self._position = position
        self._place_window(position)

    def set_destination(self, name: str | None) -> None:
        """Zet de sticky bestemming en werkt idle-weergave direct bij."""

        self._destination = name
        if self._state == RecordingState.IDLE:
            self._apply_idle_visibility()
            if self._visible:
                self._render()

    # ----- de poll-tick (GUI-thread) -----

    def _tick(self) -> None:
        if self._stop_requested:
            self.root.quit()
            return

        for state, mode in drain_status_queue():
            self._apply_state(state, mode)

        try:
            while True:
                self._main_calls.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            pass

        self._frame += 1
        if self._visible:
            self._render()

        self.root.after(POLL_INTERVAL_MS, self._tick)

    def _render(self) -> None:
        c = self.canvas
        state = self._state
        cy = INDICATOR_HEIGHT / 2
        color = STATE_COLORS.get(state, MUTED_COLOR)

        # Idle met sticky bestemming: alleen de (gedempte) naam tonen.
        if state == RecordingState.IDLE and self._destination:
            c.itemconfigure(
                self._label, text=self._destination, fill=MUTED_COLOR
            )
            c.itemconfigure(self._dot, state="hidden")
            self._render_waveform(False, MUTED_COLOR, cy)
            self._render_marching_dots(False, cy)
            c.itemconfigure(self._tag, text="", state="hidden")
            return

        # Label.
        c.itemconfigure(self._label, text=state_label(state), fill=TEXT_COLOR)

        if state == RecordingState.RECORDING:
            pulse = 0.5 + 0.5 * math.sin(self._frame * 0.35)
            r = self._dot_r * (0.7 + 0.3 * pulse)
        else:
            r = self._dot_r
        c.coords(
            self._dot,
            self._dot_cx - r, cy - r, self._dot_cx + r, cy + r,
        )
        c.itemconfigure(self._dot, state="normal", fill=color)

        recording = state == RecordingState.RECORDING
        self._render_waveform(recording, color, cy)
        self._render_marching_dots(state == RecordingState.TRANSCRIBING, cy)

        if state in (RecordingState.RECORDING, RecordingState.TRANSCRIBING):
            # ↔ en ● renderen betrouwbaar in Segoe UI (⇄/◉ niet altijd).
            tag = mode_tag(self._mode)
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

        levels = snapshot_levels()
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

    def run(self) -> None:
        """Start de poll-tick en de blokkerende Tk-mainloop (hoofdthread)."""

        self.root.after(POLL_INTERVAL_MS, self._tick)
        self.root.mainloop()

    def request_stop(self) -> None:
        self._stop_requested = True

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
