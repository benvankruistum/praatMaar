"""
macOS-indicator: native NSPanel-overlay (nonactivatingPanel) via PyObjC.

Geen focus-/key-window-diefstal — nodig voor Cmd+V auto-paste.
Zie ADR-0002. Vereist `pyobjc-framework-Cocoa` (alleen op Darwin).

Threading: de poll-tick draait als NSTimer op de main-thread-runloop.
Op macOS blokkeert `TrayIcon.run()` (pystray) die runloop; `run()` hier
plant alleen de timer. Zonder tray (tests/fallback) start `run()` zelf
`NSApp.run()`.
"""

from __future__ import annotations

import math
import queue
import sys
from typing import Any

from ._contract import (
    CANCELLED_DURATION_MS,
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
    mode_tag,
    state_label,
    TEXT_COLOR,
    WAVEFORM_GAIN,
    WINDOW_ALPHA,
    RecordingState,
    drain_status_queue,
    snapshot_levels,
)


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )


class RecordingIndicator:
    """
    Native status-pill op macOS (NSPanel).

    `root` is een verborgen tkinter-root — alleen als parent voor het
    instellingen-dialoog (`settings.open_settings_dialog`). De pill zelf is
    AppKit. Tk-events worden in de poll-tick via `update()` verwerkt.
    """

    def __init__(self, position: str = "boven-midden") -> None:
        if sys.platform != "darwin":
            raise SystemExit(
                "De macOS-indicator werkt alleen op darwin "
                "(vereist NSPanel / PyObjC)."
            )

        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSApplication,
                NSBackingStoreBuffered,
                NSBezierPath,
                NSColor,
                NSFont,
                NSPanel,
                NSScreen,
                NSTextField,
                NSView,
                NSWindowStyleMaskBorderless,
                NSWindowStyleMaskNonactivatingPanel,
            )
            from Foundation import NSMakeRect, NSTimer  # type: ignore[import-not-found]
            import tkinter as tk
        except Exception as exc:
            raise SystemExit(
                "De macOS-indicator vereist PyObjC (AppKit) en tkinter. "
                f"Installeer met: pip install 'pyobjc-framework-Cocoa'. ({exc})"
            ) from exc

        self._NSApplication = NSApplication
        self._NSColor = NSColor
        self._NSFont = NSFont
        self._NSBezierPath = NSBezierPath
        self._NSMakeRect = NSMakeRect
        self._NSTimer = NSTimer
        self._NSScreen = NSScreen
        self._NSTextField = NSTextField
        self._NSView = NSView
        self._NSPanel = NSPanel
        self._NSBackingStoreBuffered = NSBackingStoreBuffered
        self._style_mask = (
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        )

        self._tk = tk
        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._frame = 0
        self._visible = False
        self._hide_deadline_ms: float | None = None
        self._hide_elapsed_ms = 0.0
        self._stop_requested = False
        self._position = position
        self._destination: str | None = None
        self.state_listener: Any | None = None
        self._main_calls: queue.Queue[Any] = queue.Queue()
        self._timer: Any = None
        self._ticks_started = False

        try:
            # Verborgen Tk-root voor settings-Toplevel.
            self.root = tk.Tk()
            self.root.withdraw()
            self.root.title("praatMaar")

            self._build_panel()
            self.set_position(position)
        except Exception as exc:
            raise SystemExit(
                f"De opname-indicator kon niet worden geïnitialiseerd: {exc}"
            ) from exc

    def _ns_color(self, hex_color: str, alpha: float = 1.0) -> Any:
        r, g, b = _hex_to_rgb(hex_color)
        return self._NSColor.colorWithCalibratedRed_green_blue_alpha_(
            r, g, b, alpha
        )

    def _build_panel(self) -> None:
        # Zorg dat er een shared application is (pystray doet dit ook).
        self._NSApplication.sharedApplication()

        frame = self._NSMakeRect(0, 0, INDICATOR_WIDTH, INDICATOR_HEIGHT)
        panel = self._NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            self._style_mask,
            self._NSBackingStoreBuffered,
            False,
        )
        panel.setFloatingPanel_(True)
        panel.setLevel_(3)  # NSFloatingWindowLevel
        panel.setHidesOnDeactivate_(False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(self._NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setCollectionBehavior_(1 << 0 | 1 << 3)  # canJoinAllSpaces | stationary
        panel.setAlphaValue_(WINDOW_ALPHA)

        content = _PillView.alloc().initWithFrame_(frame)
        content._owner = self
        panel.setContentView_(content)

        self._panel = panel
        self._content = content

        # Labels als NSTextField bovenop de custom view (eenvoudiger dan Core Text).
        self._label_field = self._make_label(44, 18, 110, 24, bold=True)
        self._tag_field = self._make_label(
            INDICATOR_WIDTH - 120, 18, 100, 24, align_right=True
        )
        content.addSubview_(self._label_field)
        content.addSubview_(self._tag_field)

    def _make_label(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        bold: bool = False,
        align_right: bool = False,
    ) -> Any:
        field = self._NSTextField.alloc().initWithFrame_(
            self._NSMakeRect(x, y, w, h)
        )
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setEditable_(False)
        field.setSelectable_(False)
        field.setTextColor_(self._ns_color(TEXT_COLOR if bold else MUTED_COLOR))
        font = (
            self._NSFont.boldSystemFontOfSize_(13)
            if bold
            else self._NSFont.systemFontOfSize_(11)
        )
        field.setFont_(font)
        if align_right:
            field.setAlignment_(2)  # right
        return field

    def _place_window(self, position: str) -> None:
        screen = self._NSScreen.mainScreen()
        if screen is None:
            return
        visible = screen.visibleFrame()
        margin = visible.size.height * MARGIN_FRACTION
        x = visible.origin.x + (visible.size.width - INDICATOR_WIDTH) / 2

        if position == "onder-midden":
            y = visible.origin.y + margin
        else:
            y = visible.origin.y + visible.size.height - INDICATOR_HEIGHT - margin

        self._panel.setFrame_display_(
            self._NSMakeRect(x, y, INDICATOR_WIDTH, INDICATOR_HEIGHT),
            True,
        )

    def _show_window(self) -> None:
        if self._visible:
            return
        # orderFrontRegardless toont zonder key-window te worden (nonactivating).
        self._panel.orderFrontRegardless()
        self._visible = True

    def _hide_window(self) -> None:
        if not self._visible:
            return
        self._panel.orderOut_(None)
        self._visible = False

    def _apply_idle_visibility(self) -> None:
        """In idle: pill zichtbaar houden als er een sticky bestemming actief is."""

        if self._destination:
            self._show_window()
        else:
            self._hide_window()

    def _apply_state(self, state: RecordingState, mode: str) -> None:
        self._mode = mode
        self._state = state
        self._notify_listener(state, mode)
        self._hide_deadline_ms = None
        self._hide_elapsed_ms = 0.0

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
            self._content.setNeedsDisplay_(True)
            return

        self._show_window()
        self._content.setNeedsDisplay_(True)

        if state == RecordingState.CANCELLED:
            self._hide_deadline_ms = float(CANCELLED_DURATION_MS)
        elif state == RecordingState.ERROR:
            self._hide_deadline_ms = float(ERROR_DURATION_MS)

    def _transient_expired(self) -> None:
        self._hide_deadline_ms = None
        self._hide_elapsed_ms = 0.0
        self._state = RecordingState.IDLE
        self._notify_listener(RecordingState.IDLE, self._mode)
        self._apply_idle_visibility()
        self._content.setNeedsDisplay_(True)

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
                self._render_labels()
                self._content.setNeedsDisplay_(True)

    def _tick(self) -> None:
        if self._stop_requested:
            self._invalidate_timer()
            try:
                app = self._NSApplication.sharedApplication()
                app.stop_(None)
            except Exception:
                pass
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

        # Tk-events voor het instellingen-venster (deelt geen eigen mainloop).
        try:
            self.root.update()
        except Exception:
            pass

        if self._hide_deadline_ms is not None:
            self._hide_elapsed_ms += POLL_INTERVAL_MS
            if self._hide_elapsed_ms >= self._hide_deadline_ms:
                self._transient_expired()

        self._frame += 1
        if self._visible:
            self._render_labels()
            self._content.setNeedsDisplay_(True)

    def _render_labels(self) -> None:
        state = self._state

        if state == RecordingState.IDLE and self._destination:
            self._label_field.setStringValue_(self._destination)
            self._label_field.setTextColor_(self._ns_color(MUTED_COLOR))
            self._tag_field.setStringValue_("")
            self._tag_field.setHidden_(True)
            return

        self._label_field.setStringValue_(state_label(state))
        color = STATE_COLORS.get(state, MUTED_COLOR)
        self._label_field.setTextColor_(self._ns_color(color))

        if state in (RecordingState.RECORDING, RecordingState.TRANSCRIBING):
            self._tag_field.setStringValue_(mode_tag(self._mode))
            self._tag_field.setHidden_(False)
        else:
            self._tag_field.setStringValue_("")
            self._tag_field.setHidden_(True)

    def schedule_ticks(self) -> None:
        """Plant de NSTimer op de main runloop (niet-blokkerend)."""

        if self._ticks_started:
            return
        self._ticks_started = True
        interval = POLL_INTERVAL_MS / 1000.0
        self._timer = self._NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval,
            self._content,
            b"praatMaarTick:",
            None,
            True,
        )

    def prepare_external_runloop(self) -> None:
        """
        Klaarzetten voor een gedeelde Cocoa-runloop (pystray op Darwin).

        Plant de poll-timer; blokkeert niet — `TrayIcon.run()` draait NSApp.
        """

        self._external_runloop = True
        self.schedule_ticks()

    def _invalidate_timer(self) -> None:
        if self._timer is not None:
            try:
                self._timer.invalidate()
            except Exception:
                pass
            self._timer = None
        self._ticks_started = False

    def run(self) -> None:
        """
        Start de poll-timer en (fallback) een eigen NSApp-runloop.

        Normaal gebruikt `dictation.main` `prepare_external_runloop()` +
        `TrayIcon.run()` i.p.v. deze methode.
        """

        if not getattr(self, "_external_runloop", False):
            self.schedule_ticks()
            self._NSApplication.sharedApplication().run()

    def request_stop(self) -> None:
        self._stop_requested = True

    def destroy(self) -> None:
        self._invalidate_timer()
        try:
            self._panel.orderOut_(None)
            self._panel.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


# PyObjC NSView-subklasse: tekent capsule, puntje, waveform / marching dots.
# Wordt als module-niveau class gedefinieerd zodat PyObjC de objc-subclass
# kan registreren zodra AppKit beschikbaar is.


def _make_pill_view_class() -> Any:
    if sys.platform != "darwin":
        return object

    try:
        from AppKit import NSBezierPath, NSColor, NSView  # type: ignore[import-not-found]
        from Foundation import NSObject  # type: ignore[import-not-found]
    except Exception:
        return object

    class PillView(NSView):
        _owner = None

        def isOpaque(self) -> bool:  # noqa: N802 — AppKit selector
            return False

        def praatMaarTick_(self, _timer: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is not None:
                owner._tick()

        def drawRect_(self, _rect: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is None:
                return

            state = owner._state
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                self.bounds(),
                INDICATOR_HEIGHT / 2.0,
                INDICATOR_HEIGHT / 2.0,
            )
            r, g, b = _hex_to_rgb(PILL_BG)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0).setFill()
            path.fill()

            color_hex = STATE_COLORS.get(state, MUTED_COLOR)
            cr, cg, cb = _hex_to_rgb(color_hex)
            color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                cr, cg, cb, 1.0
            )

            # Statuspuntje.
            cy = INDICATOR_HEIGHT / 2.0
            if state == RecordingState.RECORDING:
                pulse = 0.5 + 0.5 * math.sin(owner._frame * 0.35)
                radius = 7.0 * (0.7 + 0.3 * pulse)
            else:
                radius = 7.0
            dot = NSBezierPath.bezierPathWithOvalInRect_(
                owner._NSMakeRect(26 - radius, cy - radius, radius * 2, radius * 2)
            )
            color.setFill()
            dot.fill()

            if state == RecordingState.RECORDING:
                self._draw_waveform(owner, color, cy)
            elif state == RecordingState.TRANSCRIBING:
                self._draw_marching_dots(owner, cy)

        def _draw_waveform(self, owner: Any, color: Any, cy: float) -> None:
            from AppKit import NSBezierPath  # type: ignore[import-not-found]

            levels = snapshot_levels()
            padded = [0.0] * (NUM_BARS - len(levels)) + levels
            x1, x2 = 150.0, 252.0
            span = x2 - x1
            bar_slot = span / NUM_BARS
            bar_w = max(2.0, bar_slot * 0.55)
            max_half = (INDICATOR_HEIGHT / 2.0) - 12.0
            color.setFill()
            for i, level in enumerate(padded):
                amp = min(1.0, level * WAVEFORM_GAIN)
                half = max(1.5, amp * max_half)
                bx = x1 + i * bar_slot
                bar = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    owner._NSMakeRect(bx, cy - half, bar_w, half * 2),
                    1.0,
                    1.0,
                )
                bar.fill()

        def _draw_marching_dots(self, owner: Any, cy: float) -> None:
            from AppKit import NSBezierPath, NSColor  # type: ignore[import-not-found]

            active = (owner._frame // 4) % 3
            for i in range(3):
                hex_c = COLOR_TRANSCRIBING if i == active else MUTED_COLOR
                r, g, b = _hex_to_rgb(hex_c)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    r, g, b, 1.0
                ).setFill()
                mx = 190 + i * 18
                NSBezierPath.bezierPathWithOvalInRect_(
                    owner._NSMakeRect(mx, cy - 4, 8, 8)
                ).fill()

    # Houd NSObject-referentie levend voor PyObjC-registratie.
    _ = NSObject
    return PillView


_PillView = _make_pill_view_class()
