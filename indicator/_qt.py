"""Qt implementation of praatMaar's always-on-top recording status pill."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ui.app import ensure_app
from ui.marshal import ui_dispatch
from ui.overlay_flags import apply_hud_window_flags
from ui.theme import TOKENS

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
    get_transcription_progress,
    mode_tag,
    normalize_indicator_position,
    preset_indicator_xy,
    snapshot_levels,
    state_label,
    transcribing_label,
)


class RecordingIndicator(QWidget):
    """Non-activating Qt status pill with the legacy indicator API."""

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
        ensure_app()
        super().__init__()
        apply_hud_window_flags(self)
        self.setFixedSize(INDICATOR_WIDTH, INDICATOR_HEIGHT)
        self.setWindowOpacity(WINDOW_ALPHA)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._frame = 0
        self._position = normalize_indicator_position(position)
        self._xy = xy
        self._on_moved = on_moved
        self._control_press_cb = on_control_press
        self._control_release_cb = on_control_release
        self.on_context_menu = on_context_menu
        self.state_listener: Any | None = None
        self._drag_offset: QPoint | None = None
        self._drag_moved = False
        self._control_held = False
        self._dest_pill = DestinationPillModel()
        self._stop_requested = False

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._transient_expired)

        self._place_window(self._position)
        # Create ui.marshal's invoker while this QWidget is on the Qt main
        # thread, before worker threads can call ``call_on_main``.
        ui_dispatch(lambda: None)

    def _screen_geometry(self) -> QRect:
        screen = self.screen() or ensure_app().primaryScreen()
        if screen is None:
            return QRect(0, 0, INDICATOR_WIDTH, INDICATOR_HEIGHT)
        return screen.availableGeometry()

    def _current_xy(self) -> tuple[int, int]:
        geometry = self._screen_geometry()
        return self.x() - geometry.x(), self.y() - geometry.y()

    def _apply_xy(self, x: int, y: int) -> None:
        geometry = self._screen_geometry()
        x, y = clamp_indicator_xy(x, y, geometry.width(), geometry.height())
        self._xy = (x, y)
        self.move(geometry.x() + x, geometry.y() + y)

    def _place_window(self, position: str) -> None:
        self._position = normalize_indicator_position(position)
        geometry = self._screen_geometry()
        if self._position == POSITION_LAST and self._xy is not None:
            self._apply_xy(*self._xy)
            return
        self._apply_xy(*preset_indicator_xy(self._position, geometry.width(), geometry.height()))

    def _show_window(self) -> None:
        if not self.isVisible():
            self.show()

    def _hide_window(self) -> None:
        if self.isVisible():
            self.hide()

    def _apply_idle_visibility(self) -> None:
        if self._dest_pill.idle_visible:
            self._show_window()
        else:
            self._hide_window()

    def _apply_state(self, state: RecordingState, mode: str) -> None:
        self._mode = mode
        self._state = state
        self._notify_listener(state, mode)
        self._hide_timer.stop()

        if state == RecordingState.RECORDING:
            self._dest_pill.on_recording_started()

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
        else:
            self._show_window()
            if state == RecordingState.CANCELLED:
                self._hide_timer.start(CANCELLED_DURATION_MS)
            elif state == RecordingState.ERROR:
                self._hide_timer.start(ERROR_DURATION_MS)
        self.update()

    def _transient_expired(self) -> None:
        self._state = RecordingState.IDLE
        self._notify_listener(RecordingState.IDLE, self._mode)
        self._apply_idle_visibility()
        self.update()

    def _notify_listener(self, state: RecordingState, mode: str) -> None:
        if self.state_listener is not None:
            try:
                self.state_listener(state, mode)
            except Exception:
                pass

    def call_on_main(self, fn: Any) -> None:
        """Queue ``fn`` on the Qt main thread."""
        ui_dispatch(fn)

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
        self._dest_pill.set_destination(name)
        if self._state == RecordingState.IDLE:
            self._apply_idle_visibility()
            self.update()

    def _tick(self) -> None:
        if self._stop_requested:
            self._stop()
            return
        for state, mode in drain_status_queue():
            self._apply_state(state, mode)
        self._frame += 1
        if self.isVisible():
            self.update()

    def run(self) -> None:
        """Start polling without owning the QApplication event loop."""
        if not self._timer.isActive():
            self._timer.start()

    def request_stop(self) -> None:
        self._stop_requested = True
        self.call_on_main(self._stop)

    def destroy(self) -> None:
        self._stop()
        self.close()
        self.deleteLater()
        self._timer = None  # type: ignore[assignment]

    def _stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._hide_timer.stop()
        self._hide_window()

    def _control_rect(self) -> QRect:
        if self._state == RecordingState.RECORDING:
            return QRect(INDICATOR_WIDTH - 40, 8, 32, INDICATOR_HEIGHT - 16)
        return QRect(INDICATOR_WIDTH - 72, 8, 28, INDICATOR_HEIGHT - 16)

    def _dismiss_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - 40, 8, 32, INDICATOR_HEIGHT - 16)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.RightButton:
            if self.on_context_menu is not None:
                point = event.globalPosition().toPoint()
                try:
                    self.on_context_menu(point.x(), point.y())
                except Exception:
                    pass
            event.accept()
            return

        if event.button() != Qt.LeftButton:
            event.ignore()
            return

        if self._state == RecordingState.IDLE and self._dest_pill.idle_visible:
            if self._dismiss_rect().contains(event.position().toPoint()):
                self._dest_pill.dismiss()
                self._apply_idle_visibility()
                self.update()
                event.accept()
                return
            if self._control_rect().contains(event.position().toPoint()):
                self._control_held = True
                self._invoke_callback(self._control_press_cb)
                event.accept()
                return
        elif self._state == RecordingState.RECORDING and self._control_rect().contains(
            event.position().toPoint()
        ):
            self._control_held = True
            self._invoke_callback(self._control_press_cb)
            event.accept()
            return

        self._drag_offset = event.globalPosition().toPoint() - self.pos()
        self._drag_moved = False
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is None:
            event.ignore()
            return
        target = event.globalPosition().toPoint() - self._drag_offset
        self._apply_xy(
            target.x() - self._screen_geometry().x(),
            target.y() - self._screen_geometry().y(),
        )
        self._drag_moved = True
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        if self._control_held:
            self._control_held = False
            self._invoke_callback(self._control_release_cb)
        elif self._drag_offset is not None and self._drag_moved:
            x, y = self._current_xy()
            self._position = POSITION_LAST
            self._xy = (x, y)
            self._invoke_callback(self._on_moved, POSITION_LAST, x, y)
        self._drag_offset = None
        self._drag_moved = False
        event.accept()

    @staticmethod
    def _invoke_callback(callback: Any, *args: Any) -> None:
        if callback is not None:
            try:
                callback(*args)
            except Exception:
                pass

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(PILL_BG))
        painter.drawRoundedRect(self.rect(), INDICATOR_HEIGHT / 2, INDICATOR_HEIGHT / 2)

        if self._state == RecordingState.IDLE and self._dest_pill.idle_visible:
            self._paint_idle_destination(painter)
            return

        color = QColor(STATE_COLORS.get(self._state, MUTED_COLOR))
        self._paint_status_dot(painter, color)
        painter.setPen(QColor(TEXT_COLOR))
        painter.drawText(
            QRect(44, 0, 106, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._status_label(),
        )

        if self._state == RecordingState.RECORDING:
            self._paint_waveform(painter, color)
            painter.setBrush(QColor(TEXT_COLOR))
            painter.drawRect(INDICATOR_WIDTH - 27, 25, 10, 10)
        elif self._state == RecordingState.TRANSCRIBING:
            self._paint_marching_dots(painter)

        if self._state in (RecordingState.RECORDING, RecordingState.TRANSCRIBING):
            painter.setPen(QColor(TOKENS["accent"] if self._mode == "meeting" else MUTED_COLOR))
            painter.drawText(
                QRect(255, 0, 76, INDICATOR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignRight,
                mode_tag(self._mode),
            )

    def _paint_idle_destination(self, painter: QPainter) -> None:
        painter.setBrush(QColor(MUTED_COLOR))
        painter.drawRect(18, 28, 16, 8)
        painter.drawRect(18, 25, 8, 4)
        painter.setPen(QColor(MUTED_COLOR))
        painter.drawText(
            QRect(44, 0, 205, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignLeft,
            destination_display_name(self._dest_pill.name),
        )
        painter.setBrush(QColor(COLOR_RECORDING))
        painter.drawEllipse(INDICATOR_WIDTH - 64, 24, 12, 12)
        painter.setPen(QColor(MUTED_COLOR))
        painter.drawText(
            self._dismiss_rect(),
            Qt.AlignCenter,
            "×",
        )

    def _paint_status_dot(self, painter: QPainter, color: QColor) -> None:
        radius = 7.0
        if self._state == RecordingState.RECORDING:
            radius *= 0.7 + 0.3 * (0.5 + 0.5 * math.sin(self._frame * 0.35))
        painter.setBrush(color)
        painter.drawEllipse(
            int(26 - radius),
            int(INDICATOR_HEIGHT / 2 - radius),
            int(radius * 2),
            int(radius * 2),
        )

    def _paint_waveform(self, painter: QPainter, color: QColor) -> None:
        levels = snapshot_levels()
        padded = [0.0] * (NUM_BARS - len(levels)) + levels
        x1, x2 = 150.0, 252.0
        bar_slot = (x2 - x1) / NUM_BARS
        bar_width = max(2.0, bar_slot * 0.55)
        max_half = INDICATOR_HEIGHT / 2 - 12
        painter.setBrush(color)
        for index, level in enumerate(padded):
            half = max(1.5, min(1.0, level * WAVEFORM_GAIN) * max_half)
            painter.drawRoundedRect(
                int(x1 + index * bar_slot),
                int(INDICATOR_HEIGHT / 2 - half),
                int(bar_width),
                int(half * 2),
                1,
                1,
            )

    def _paint_marching_dots(self, painter: QPainter) -> None:
        active = (self._frame // 4) % 3
        for index in range(3):
            painter.setBrush(QColor(COLOR_TRANSCRIBING if index == active else MUTED_COLOR))
            painter.drawEllipse(190 + index * 18, 26, 8, 8)

    def _status_label(self) -> str:
        if self._state == RecordingState.TRANSCRIBING:
            return transcribing_label(get_transcription_progress())
        return state_label(self._state)
