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
    COLOR_RECORDING,
    COLOR_TRANSCRIBING,
    ERROR_DURATION_MS,
    INDICATOR_HEIGHT,
    INDICATOR_WIDTH,
    MUTED_COLOR,
    NUM_BARS,
    PILL_BG,
    POLL_INTERVAL_MS,
    POSITION_BOTTOM,
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
    snapshot_levels,
    state_label,
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

    Pure AppKit — geen tkinter. Instellingen draait in een apart Tk-proces
    (`settings_process.run_settings_subprocess`) om Cocoa/Tk-runloop-crashes
    te vermijden.
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
        if sys.platform != "darwin":
            raise SystemExit(
                "De macOS-indicator werkt alleen op darwin (vereist NSPanel / PyObjC)."
            )

        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSApplication,
                NSBackingStoreBuffered,
                NSBezierPath,
                NSButton,
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
        except Exception as exc:
            raise SystemExit(
                "De macOS-indicator vereist PyObjC (AppKit). "
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
        self._NSButton = NSButton
        self._NSView = NSView
        self._NSPanel = NSPanel
        self._NSBackingStoreBuffered = NSBackingStoreBuffered
        self._style_mask = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel

        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._frame = 0
        self._visible = False
        self._hide_deadline_ms: float | None = None
        self._hide_elapsed_ms = 0.0
        self._stop_requested = False
        self._position = normalize_indicator_position(position)
        self._xy = xy
        self._on_moved = on_moved
        self._control_press_cb = on_control_press
        self._control_release_cb = on_control_release
        self.on_context_menu = on_context_menu
        self._drag: dict[str, Any] | None = None
        self._control_held = False
        self._control_kind: str | None = None
        self._dest_pill = DestinationPillModel()
        self.state_listener: Any | None = None
        self._main_calls: queue.Queue[Any] = queue.Queue()
        self._timer: Any = None
        self._ticks_started = False

        try:
            self._build_panel()
            self.set_position(self._position)
        except Exception as exc:
            raise SystemExit(f"De opname-indicator kon niet worden geïnitialiseerd: {exc}") from exc

    def _ns_color(self, hex_color: str, alpha: float = 1.0) -> Any:
        r, g, b = _hex_to_rgb(hex_color)
        return self._NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha)

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
        self._tag_field = self._make_label(INDICATOR_WIDTH - 150, 18, 80, 24, align_right=True)
        content.addSubview_(self._label_field)
        content.addSubview_(self._tag_field)

        self._dismiss_btn = self._make_dismiss_button()
        content.addSubview_(self._dismiss_btn)
        self._dismiss_btn.setHidden_(True)

    def _make_dismiss_button(self) -> Any:
        btn = self._NSButton.alloc().initWithFrame_(
            self._NSMakeRect(INDICATOR_WIDTH - 36, 16, 28, 28)
        )
        btn.setBordered_(False)
        btn.setTitle_("×")
        btn.setFont_(self._NSFont.systemFontOfSize_(16))
        btn.setTarget_(self._content)
        btn.setAction_(b"dismissClicked:")
        return btn

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
        field = self._NSTextField.alloc().initWithFrame_(self._NSMakeRect(x, y, w, h))
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setEditable_(False)
        field.setSelectable_(False)
        field.setTextColor_(self._ns_color(TEXT_COLOR if bold else MUTED_COLOR))
        font = (
            self._NSFont.boldSystemFontOfSize_(13) if bold else self._NSFont.systemFontOfSize_(11)
        )
        field.setFont_(font)
        if align_right:
            field.setAlignment_(2)  # right
        return field

    def _screen_metrics(self) -> tuple[Any, float, float] | None:
        screen = self._NSScreen.mainScreen()
        if screen is None:
            return None
        frame = screen.frame()
        return frame, float(frame.size.width), float(frame.size.height)

    def _top_left_from_cocoa(self, cocoa_x: float, cocoa_y: float) -> tuple[int, int]:
        metrics = self._screen_metrics()
        if metrics is None:
            return 0, 0
        frame, _w, height = metrics
        x = int(round(cocoa_x - frame.origin.x))
        y = int(round(frame.origin.y + height - cocoa_y - INDICATOR_HEIGHT))
        return x, y

    def _cocoa_from_top_left(self, x: int, y: int) -> tuple[float, float]:
        metrics = self._screen_metrics()
        if metrics is None:
            return float(x), float(y)
        frame, _w, height = metrics
        cocoa_x = frame.origin.x + x
        cocoa_y = frame.origin.y + height - y - INDICATOR_HEIGHT
        return float(cocoa_x), float(cocoa_y)

    def _apply_xy(self, x: int, y: int) -> None:
        metrics = self._screen_metrics()
        if metrics is None:
            return
        _frame, screen_w, screen_h = metrics
        x, y = clamp_indicator_xy(x, y, int(screen_w), int(screen_h))
        self._xy = (x, y)
        cocoa_x, cocoa_y = self._cocoa_from_top_left(x, y)
        self._panel.setFrame_display_(
            self._NSMakeRect(cocoa_x, cocoa_y, INDICATOR_WIDTH, INDICATOR_HEIGHT),
            True,
        )

    def _place_window(self, position: str) -> None:
        position = normalize_indicator_position(position)
        self._position = position
        screen = self._NSScreen.mainScreen()
        if screen is None:
            return

        if position == POSITION_LAST and self._xy is not None:
            self._apply_xy(self._xy[0], self._xy[1])
            return

        visible = screen.visibleFrame()
        margin = visible.size.height * 0.10
        cocoa_x = visible.origin.x + (visible.size.width - INDICATOR_WIDTH) / 2
        if position == POSITION_BOTTOM:
            cocoa_y = visible.origin.y + margin
        else:
            cocoa_y = visible.origin.y + visible.size.height - INDICATOR_HEIGHT - margin
        top_left = self._top_left_from_cocoa(cocoa_x, cocoa_y)
        self._apply_xy(top_left[0], top_left[1])

    def _begin_drag(self, _event: Any) -> None:
        from AppKit import NSEvent  # type: ignore[import-not-found]

        mouse = NSEvent.mouseLocation()
        frame = self._panel.frame()
        self._drag = {
            "dx": float(mouse.x) - float(frame.origin.x),
            "dy": float(mouse.y) - float(frame.origin.y),
            "start_x": float(mouse.x),
            "start_y": float(mouse.y),
            "moved": False,
        }

    def _update_drag(self, _event: Any) -> None:
        if self._drag is None:
            return
        from AppKit import NSEvent  # type: ignore[import-not-found]

        mouse = NSEvent.mouseLocation()
        if (
            abs(float(mouse.x) - self._drag["start_x"]) > 1
            or abs(float(mouse.y) - self._drag["start_y"]) > 1
        ):
            self._drag["moved"] = True
        cocoa_x = float(mouse.x) - self._drag["dx"]
        cocoa_y = float(mouse.y) - self._drag["dy"]
        x, y = self._top_left_from_cocoa(cocoa_x, cocoa_y)
        self._apply_xy(x, y)

    def _end_drag(self) -> None:
        drag = self._drag
        self._drag = None
        if drag is None or not drag.get("moved"):
            return
        frame = self._panel.frame()
        x, y = self._top_left_from_cocoa(float(frame.origin.x), float(frame.origin.y))
        self._position = POSITION_LAST
        self._xy = (x, y)
        if self._on_moved is not None:
            try:
                self._on_moved(POSITION_LAST, x, y)
            except Exception:
                pass

    def _show_window(self) -> None:
        if self._visible:
            return
        # orderFrontRegardless toont zonder key-window te worden (nonactivating).
        self._panel.orderFrontRegardless()
        self._visible = True
        self._sync_mouse_events()

    def _hide_window(self) -> None:
        if not self._visible:
            return
        self._panel.orderOut_(None)
        self._visible = False
        self._sync_mouse_events()

    def _apply_idle_visibility(self) -> None:
        """In idle: pill zichtbaar als sticky bestemming actief én niet weggeklikt."""

        if self._dest_pill.idle_visible:
            self._show_window()
        else:
            self._hide_window()
        self._sync_mouse_events()

    def _sync_mouse_events(self) -> None:
        """Muis doorlaten wanneer de pill zichtbaar is (slepen + ×)."""

        self._panel.setIgnoresMouseEvents_(not self._visible)

    def _apply_state(self, state: RecordingState, mode: str) -> None:
        self._mode = mode
        self._state = state
        self._notify_listener(state, mode)
        self._hide_deadline_ms = None
        self._hide_elapsed_ms = 0.0

        if state == RecordingState.RECORDING:
            self._dest_pill.on_recording_started()

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
            self._content.setNeedsDisplay_(True)
            return

        self._show_window()
        self._sync_mouse_events()
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
                self._render_labels()
                self._content.setNeedsDisplay_(True)

    def _on_dismiss_click(self) -> None:
        self._dest_pill.dismiss()
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

        if self._hide_deadline_ms is not None:
            self._hide_elapsed_ms += POLL_INTERVAL_MS
            if self._hide_elapsed_ms >= self._hide_deadline_ms:
                self._transient_expired()

        self._frame += 1
        if self._visible:
            self._render_labels()
            self._content.setNeedsDisplay_(True)

    def _control_rect(self) -> Any:
        if self._control_kind == "stop":
            return self._NSMakeRect(INDICATOR_WIDTH - 36, 16, 28, 28)
        return self._NSMakeRect(INDICATOR_WIDTH - 72, 16, 28, 28)

    def _hit_control(self, point: Any) -> bool:
        if self._control_kind is None:
            return False
        return self._control_rect().containsPoint_(point)

    def _set_control_visible(self, kind: str | None) -> None:
        self._control_kind = kind

    def _fire_control_press(self) -> None:
        self._drag = None
        self._control_held = True
        if self._control_press_cb is not None:
            try:
                self._control_press_cb()
            except Exception:
                pass

    def _fire_control_release(self) -> None:
        if not self._control_held:
            return
        self._control_held = False
        if self._control_release_cb is not None:
            try:
                self._control_release_cb()
            except Exception:
                pass

    def _render_labels(self) -> None:
        state = self._state

        if state == RecordingState.IDLE and self._dest_pill.idle_visible:
            self._label_field.setStringValue_(destination_display_name(self._dest_pill.name))
            self._label_field.setTextColor_(self._ns_color(MUTED_COLOR))
            self._tag_field.setStringValue_("")
            self._tag_field.setHidden_(True)
            self._dismiss_btn.setHidden_(False)
            self._set_control_visible("record")
            return

        self._dismiss_btn.setHidden_(True)
        self._label_field.setStringValue_(state_label(state))
        color = STATE_COLORS.get(state, MUTED_COLOR)
        self._label_field.setTextColor_(self._ns_color(color))

        if state == RecordingState.RECORDING:
            self._set_control_visible("stop")
        else:
            self._set_control_visible(None)

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
        self._timer = (
            self._NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                interval,
                self._content,
                b"praatMaarTick:",
                None,
                True,
            )
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

        def dismissClicked_(self, _sender: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is not None:
                owner._drag = None
                owner._control_held = False
                owner._on_dismiss_click()

        def mouseDown_(self, event: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is None:
                return
            point = self.convertPoint_fromView_(event.locationInWindow(), None)
            if owner._hit_control(point):
                owner._fire_control_press()
                return
            owner._begin_drag(event)

        def mouseDragged_(self, event: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is not None and not owner._control_held:
                owner._update_drag(event)

        def mouseUp_(self, _event: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is None:
                return
            if owner._control_held:
                owner._fire_control_release()
                return
            owner._end_drag()

        def rightMouseDown_(self, event: Any) -> None:  # noqa: N802
            owner = self._owner
            if owner is None or owner.on_context_menu is None:
                return
            owner._drag = None
            owner._control_held = False
            try:
                from AppKit import NSEvent  # type: ignore[import-not-found]

                point = NSEvent.mouseLocation()
                # Cocoa bottom-left → top-left voor eventuele callers.
                screen = owner._NSScreen.mainScreen()
                if screen is not None:
                    frame = screen.frame()
                    x = int(round(point.x))
                    y = int(round(frame.size.height - point.y))
                else:
                    x, y = int(point.x), int(point.y)
                owner.on_context_menu(x, y)
            except Exception:
                pass

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

            cy = INDICATOR_HEIGHT / 2.0

            # Idle + bestemming: map-icoon i.p.v. statuspuntje.
            if state == RecordingState.IDLE and owner._dest_pill.idle_visible:
                self._draw_folder_icon(owner, cy)
                self._draw_control(owner)
                return

            color_hex = STATE_COLORS.get(state, MUTED_COLOR)
            cr, cg, cb = _hex_to_rgb(color_hex)
            color = NSColor.colorWithCalibratedRed_green_blue_alpha_(cr, cg, cb, 1.0)

            # Statuspuntje.
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
                self._draw_control(owner)
            elif state == RecordingState.TRANSCRIBING:
                self._draw_marching_dots(owner, cy)

        def _draw_control(self, owner: Any) -> None:
            if owner._control_kind is None:
                return
            from AppKit import NSBezierPath, NSColor  # type: ignore[import-not-found]

            rect = owner._control_rect()
            cx = rect.origin.x + rect.size.width / 2.0
            cy = rect.origin.y + rect.size.height / 2.0
            if owner._control_kind == "stop":
                rr, gg, bb = _hex_to_rgb(TEXT_COLOR)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(rr, gg, bb, 1.0).setFill()
                stop = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    owner._NSMakeRect(cx - 5, cy - 5, 10, 10),
                    1.5,
                    1.5,
                )
                stop.fill()
            else:
                rr, gg, bb = _hex_to_rgb(COLOR_RECORDING)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(rr, gg, bb, 1.0).setFill()
                dot = NSBezierPath.bezierPathWithOvalInRect_(
                    owner._NSMakeRect(cx - 6, cy - 6, 12, 12)
                )
                dot.fill()

        def _draw_folder_icon(self, owner: Any, cy: float) -> None:
            from AppKit import NSBezierPath, NSColor  # type: ignore[import-not-found]

            r, g, b = _hex_to_rgb(MUTED_COLOR)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0).setFill()
            left = 18.0
            tab = NSBezierPath.bezierPath()
            tab.moveToPoint_((left, cy - 5))
            tab.lineToPoint_((left + 6, cy - 5))
            tab.lineToPoint_((left + 8, cy - 2))
            tab.lineToPoint_((left, cy - 2))
            tab.closePath()
            tab.fill()
            body = NSBezierPath.bezierPathWithRect_(owner._NSMakeRect(left, cy - 2, 16, 8))
            body.fill()

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
                NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0).setFill()
                mx = 190 + i * 18
                NSBezierPath.bezierPathWithOvalInRect_(owner._NSMakeRect(mx, cy - 4, 8, 8)).fill()

    # Houd NSObject-referentie levend voor PyObjC-registratie.
    _ = NSObject
    return PillView


_PillView = _make_pill_view_class()
