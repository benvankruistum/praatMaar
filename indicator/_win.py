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
    MUTED_COLOR,
    NUM_BARS,
    PILL_BG,
    POLL_INTERVAL_MS,
    POSITION_LAST,
    STATE_COLORS,
    TEXT_COLOR,
    WAVEFORM_GAIN,
    WINDOW_ALPHA,
    DestinationPillModel,
    RecordingState,
    clamp_indicator_xy,
    destination_display_name,
    drain_status_queue,
    mode_tag,
    normalize_indicator_position,
    preset_indicator_xy,
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

    def __init__(
        self,
        position: str = "boven-midden",
        *,
        xy: tuple[int, int] | None = None,
        on_moved: Any | None = None,
        on_control_press: Any | None = None,
        on_control_release: Any | None = None,
        on_context_menu: Any | None = None,
    ) -> None:
        if sys.platform != "win32":
            raise SystemExit(
                "De Windows-indicator werkt alleen op win32 (vereist de WS_EX_NOACTIVATE-shim)."
            )

        import tkinter as tk

        self._tk = tk
        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._frame = 0
        self._visible = False
        self._hide_after_id: str | None = None
        self._stop_requested = False
        self._position = normalize_indicator_position(position)
        self._xy = xy
        self._on_moved = on_moved
        self._control_press_cb = on_control_press
        self._control_release_cb = on_control_release
        self.on_context_menu = on_context_menu
        self._drag: dict[str, Any] | None = None
        self._control_held = False
        self._dest_pill = DestinationPillModel()

        # Wordt bij elke toestandswissel aangeroepen (op de hoofdthread); door
        # main() bedraad naar de tray zodat de pill de enige toestandseigenaar is.
        self.state_listener: Any | None = None

        # Thread-veilige marshalling: andere threads (bijv. de tray) leggen hier
        # een callable neer; de poll-tick voert het uit op de hoofdthread.
        self._main_calls: queue.Queue[Any] = queue.Queue()

        try:
            self._build_window(self._position)
        except Exception as exc:
            raise SystemExit(f"De opname-indicator kon niet worden geïnitialiseerd: {exc}") from exc

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
        self.canvas.bind("<ButtonPress-1>", self._on_drag_press)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_release)
        self.canvas.bind("<ButtonPress-3>", self._on_context_menu)
        self.canvas.bind("<ButtonRelease-3>", lambda _e: "break")

        self.root.update_idletasks()
        self._hwnd = self.root.winfo_id()

        self._user32 = _configure_user32()
        ex_style = self._user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        self._user32.SetWindowLongW(
            self._hwnd,
            GWL_EXSTYLE,
            ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        )

    def _screen_size(self) -> tuple[int, int]:
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _current_xy(self) -> tuple[int, int]:
        self.root.update_idletasks()
        return int(self.root.winfo_x()), int(self.root.winfo_y())

    def _apply_xy(self, x: int, y: int) -> None:
        screen_w, screen_h = self._screen_size()
        x, y = clamp_indicator_xy(x, y, screen_w, screen_h)
        self._xy = (x, y)
        self.root.geometry(f"{INDICATOR_WIDTH}x{INDICATOR_HEIGHT}+{x}+{y}")

    def _place_window(self, position: str) -> None:
        position = normalize_indicator_position(position)
        self._position = position
        screen_w, screen_h = self._screen_size()
        if position == POSITION_LAST and self._xy is not None:
            self._apply_xy(self._xy[0], self._xy[1])
            return
        x, y = preset_indicator_xy(position, screen_w, screen_h)
        self._apply_xy(x, y)

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

        # Map-icoon (idle + bestemming); geometrie i.p.v. emoji.
        self._folder_items = self._create_folder_icon(18, cy)

        self._label = c.create_text(44, cy, text="", anchor="w", fill=TEXT_COLOR, font=LABEL_FONT)

        self._wf_x1 = 150
        self._wf_x2 = 252
        self._bars = []
        span = self._wf_x2 - self._wf_x1
        bar_slot = span / NUM_BARS
        bar_w = max(2, bar_slot * 0.55)
        for i in range(NUM_BARS):
            bx = self._wf_x1 + i * bar_slot
            bar = c.create_rectangle(
                bx,
                cy - 1,
                bx + bar_w,
                cy + 1,
                fill=COLOR_RECORDING,
                outline="",
                state="hidden",
            )
            self._bars.append(bar)

        self._mdots = []
        for i in range(3):
            mx = 190 + i * 18
            dot = c.create_oval(
                mx,
                cy - 4,
                mx + 8,
                cy + 4,
                fill=MUTED_COLOR,
                outline="",
                state="hidden",
            )
            self._mdots.append(dot)

        self._tag = c.create_text(
            INDICATOR_WIDTH - 52,
            cy,
            text="",
            anchor="e",
            fill=MUTED_COLOR,
            font=TAG_FONT,
        )

        # Opname-/stopknop — idle+bestemming (●) of tijdens opname (■).
        self._control_hit = c.create_rectangle(
            INDICATOR_WIDTH - 72,
            8,
            INDICATOR_WIDTH - 44,
            h - 8,
            fill="",
            outline="",
            tags=("control",),
            state="hidden",
        )
        self._control_btn = c.create_text(
            INDICATOR_WIDTH - 58,
            cy,
            text="●",
            anchor="center",
            fill=COLOR_RECORDING,
            font=("Segoe UI", 14),
            tags=("control",),
            state="hidden",
        )
        c.tag_bind("control", "<ButtonPress-1>", self._on_control_press)
        c.tag_bind("control", "<ButtonRelease-1>", self._on_control_release)
        c.tag_raise("control")

        # Sluitknop (×) — alleen idle + bestemming; ruime hit-area.
        self._dismiss_hit = c.create_rectangle(
            INDICATOR_WIDTH - 40,
            8,
            INDICATOR_WIDTH - 8,
            h - 8,
            fill="",
            outline="",
            tags=("dismiss",),
            state="hidden",
        )
        self._dismiss_btn = c.create_text(
            INDICATOR_WIDTH - 22,
            cy,
            text="×",
            anchor="center",
            fill=MUTED_COLOR,
            font=("Segoe UI", 14),
            tags=("dismiss",),
            state="hidden",
        )
        c.tag_bind("dismiss", "<Button-1>", self._on_dismiss_click)
        c.tag_raise("dismiss")

    def _on_context_menu(self, event: Any) -> str:
        self._drag = None
        if self.on_context_menu is not None:
            try:
                self.on_context_menu(int(event.x_root), int(event.y_root))
            except Exception:
                pass
        return "break"

    def _on_drag_press(self, event: Any) -> None:
        current = self.canvas.find_withtag("current")
        if current:
            tags = self.canvas.gettags(current[0])
            if "dismiss" in tags or "control" in tags:
                return
        self._drag = {
            "offset_x": event.x_root - self.root.winfo_x(),
            "offset_y": event.y_root - self.root.winfo_y(),
            "moved": False,
        }

    def _on_drag_motion(self, event: Any) -> None:
        if self._drag is None:
            return
        x = int(event.x_root - self._drag["offset_x"])
        y = int(event.y_root - self._drag["offset_y"])
        self._drag["moved"] = True
        self._apply_xy(x, y)

    def _on_drag_release(self, _event: Any = None) -> None:
        drag = self._drag
        self._drag = None
        if drag is None or not drag.get("moved"):
            return
        x, y = self._current_xy()
        self._position = POSITION_LAST
        self._xy = (x, y)
        if self._on_moved is not None:
            try:
                self._on_moved(POSITION_LAST, x, y)
            except Exception:
                pass

    def _create_folder_icon(self, left: float, cy: float) -> list[int]:
        """Tekent een klein map-icoon; items starten hidden."""

        c = self.canvas
        # Tab + body (eenvoudige geometrie, ~16×12).
        tab = c.create_polygon(
            left,
            cy - 5,
            left + 6,
            cy - 5,
            left + 8,
            cy - 2,
            left,
            cy - 2,
            fill=MUTED_COLOR,
            outline="",
            tags=("folder",),
            state="hidden",
        )
        body = c.create_rectangle(
            left,
            cy - 2,
            left + 16,
            cy + 6,
            fill=MUTED_COLOR,
            outline="",
            tags=("folder",),
            state="hidden",
        )
        return [tab, body]

    def _on_control_press(self, _event: Any = None) -> str:
        self._drag = None
        self._control_held = True
        if self._control_press_cb is not None:
            try:
                self._control_press_cb()
            except Exception:
                pass
        return "break"

    def _on_control_release(self, _event: Any = None) -> str:
        if not self._control_held:
            return "break"
        self._control_held = False
        if self._control_release_cb is not None:
            try:
                self._control_release_cb()
            except Exception:
                pass
        return "break"

    def _set_control_visible(self, kind: str | None) -> None:
        """kind: 'record' | 'stop' | None."""

        c = self.canvas
        if kind is None:
            c.itemconfigure(self._control_hit, state="hidden")
            c.itemconfigure(self._control_btn, state="hidden")
            return
        if kind == "stop":
            # Zelfde plek als × tijdens opname (× is dan verborgen).
            c.coords(self._control_hit, INDICATOR_WIDTH - 40, 8, INDICATOR_WIDTH - 8, INDICATOR_HEIGHT - 8)
            c.coords(self._control_btn, INDICATOR_WIDTH - 22, INDICATOR_HEIGHT / 2)
            c.itemconfigure(self._control_btn, text="■", fill=TEXT_COLOR)
        else:
            c.coords(self._control_hit, INDICATOR_WIDTH - 72, 8, INDICATOR_WIDTH - 44, INDICATOR_HEIGHT - 8)
            c.coords(self._control_btn, INDICATOR_WIDTH - 58, INDICATOR_HEIGHT / 2)
            c.itemconfigure(self._control_btn, text="●", fill=COLOR_RECORDING)
        c.itemconfigure(self._control_hit, state="normal")
        c.itemconfigure(self._control_btn, state="normal")

    def _on_dismiss_click(self, _event: Any = None) -> str:
        """Verberg de bestemmingspill; sticky bestemming blijft actief."""

        self._drag = None
        self._dest_pill.dismiss()
        self._apply_idle_visibility()
        if self._visible:
            self._render()
        return "break"

    @staticmethod
    def _round_rect_points(x1: float, y1: float, x2: float, y2: float, r: float) -> list[float]:
        return [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]

    def _show_window(self) -> None:
        if self._visible:
            return

        self.root.deiconify()
        self.root.update_idletasks()
        self._user32.SetWindowPos(
            self._hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        self._visible = True

    def _hide_window(self) -> None:
        if not self._visible:
            return

        self.root.withdraw()
        self._visible = False

    def _apply_idle_visibility(self) -> None:
        """In idle: pill zichtbaar als sticky bestemming actief én niet weggeklikt."""

        if self._dest_pill.idle_visible:
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

        if state == RecordingState.RECORDING:
            self._dest_pill.on_recording_started()

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
            if self._visible:
                self._render()
            return

        self._show_window()

        if state == RecordingState.CANCELLED:
            self._hide_after_id = self.root.after(CANCELLED_DURATION_MS, self._transient_expired)
        elif state == RecordingState.ERROR:
            self._hide_after_id = self.root.after(ERROR_DURATION_MS, self._transient_expired)

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

    def set_position(
        self,
        position: str,
        *,
        xy: tuple[int, int] | None = None,
    ) -> None:
        if xy is not None:
            self._xy = xy
        self._place_window(position)

    def set_destination(self, name: str | None) -> None:
        """Zet de sticky bestemming en werkt idle-weergave direct bij."""

        self._dest_pill.set_destination(name)
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

        # Idle met sticky bestemming: map-icoon + naam + opname + ×.
        if state == RecordingState.IDLE and self._dest_pill.idle_visible:
            c.itemconfigure(
                self._label,
                text=destination_display_name(self._dest_pill.name),
                fill=MUTED_COLOR,
            )
            c.itemconfigure(self._dot, state="hidden")
            for item in self._folder_items:
                c.itemconfigure(item, state="normal")
            c.itemconfigure(self._dismiss_hit, state="normal")
            c.itemconfigure(self._dismiss_btn, state="normal")
            self._set_control_visible("record")
            self._render_waveform(False, MUTED_COLOR, cy)
            self._render_marching_dots(False, cy)
            c.itemconfigure(self._tag, text="", state="hidden")
            return

        for item in self._folder_items:
            c.itemconfigure(item, state="hidden")
        c.itemconfigure(self._dismiss_hit, state="hidden")
        c.itemconfigure(self._dismiss_btn, state="hidden")

        # Label.
        c.itemconfigure(self._label, text=state_label(state), fill=TEXT_COLOR)

        if state == RecordingState.RECORDING:
            pulse = 0.5 + 0.5 * math.sin(self._frame * 0.35)
            r = self._dot_r * (0.7 + 0.3 * pulse)
            self._set_control_visible("stop")
        else:
            r = self._dot_r
            self._set_control_visible(None)
        c.coords(
            self._dot,
            self._dot_cx - r,
            cy - r,
            self._dot_cx + r,
            cy + r,
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

    def _render_waveform(self, visible: bool, color: str, cy: float) -> None:
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
