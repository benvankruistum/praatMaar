"""Qt implementation of praatMaar's always-on-top recording status pill."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

import i18n
from ui.app import ensure_app
from ui.marshal import ui_dispatch
from ui.overlay_flags import apply_hud_window_flags

from ._contract import (
    CANCELLED_DURATION_MS,
    COLOR_CANCELLED,
    COLOR_CHUNK_LED_FIXED,
    COLOR_CHUNK_LED_IDLE,
    COLOR_CHUNK_LED_VAD,
    COLOR_ERROR,
    COLOR_ERROR_LABEL,
    COLOR_MEETING_DOT,
    COLOR_MEETING_TEXT,
    COLOR_RECORDING,
    COLOR_TRANSCRIBING,
    ERROR_DURATION_MS,
    INDICATOR_HEIGHT,
    INDICATOR_WIDTH,
    MUTED_COLOR,
    NUM_BARS,
    PILL_BG,
    PILL_BG_ERROR,
    POLL_INTERVAL_MS,
    POSITION_LAST,
    SUBTLE_COLOR,
    TAG_TEXT_COLOR,
    TEXT_COLOR,
    WAVEFORM_GAIN,
    WINDOW_ALPHA,
    DestinationPillModel,
    RecordingState,
    chunk_led_snapshot,
    clamp_indicator_xy,
    destination_display_name,
    drain_status_queue,
    get_transcription_progress,
    normalize_indicator_position,
    preset_indicator_xy,
    snapshot_levels,
    state_label,
)

_BTN = 32
_BTN_Y = (INDICATOR_HEIGHT - _BTN) // 2
_RIGHT_PAD = 8


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
        self._hotkey_label: str | None = None

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

    def set_hotkey_label(self, text: str | None) -> None:
        """Set the shortcut shown in the idle subline (e.g. ``Ctrl + Space``)."""
        self._hotkey_label = (text or "").strip() or None
        if self.isVisible():
            self.update()

    def _tick(self) -> None:
        if self._stop_requested:
            self._stop()
            return
        for state, mode, _hint in drain_status_queue():
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

    def _dismiss_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - _RIGHT_PAD - _BTN, _BTN_Y, _BTN, _BTN)

    def _record_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - _RIGHT_PAD - _BTN * 2 - 10, _BTN_Y, _BTN, _BTN)

    def _stop_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - _RIGHT_PAD - _BTN, _BTN_Y, _BTN, _BTN)

    def _control_rect(self) -> QRect:
        if self._state == RecordingState.RECORDING:
            return self._stop_rect()
        return self._record_rect()

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

    # ---- painting (canvas #2a) ---------------------------------------
    _CY = INDICATOR_HEIGHT / 2
    _LEFT = 16

    def _font(self, px: int, *, bold: bool = False) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(px)
        if bold:
            font.setWeight(QFont.Weight.DemiBold)
        return font

    def _border_color(self) -> QColor:
        state = self._state
        if state == RecordingState.RECORDING:
            return QColor(255, 92, 87, 61)
        if state == RecordingState.TRANSCRIBING:
            return QColor(255, 176, 32, 61)
        if state == RecordingState.ERROR:
            return QColor(255, 107, 107, 87)
        if state == RecordingState.CANCELLED:
            return QColor(255, 255, 255, 20)
        return QColor(255, 255, 255, 26)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, INDICATOR_WIDTH - 1.0, INDICATOR_HEIGHT - 1.0)
        radius = INDICATOR_HEIGHT / 2
        bg = PILL_BG_ERROR if self._state == RecordingState.ERROR else PILL_BG
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(rect, radius, radius)
        border = QPen(self._border_color())
        border.setWidthF(1.0)
        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        state = self._state
        if state == RecordingState.IDLE:
            if self._dest_pill.idle_visible:
                self._paint_idle(painter)
        elif state == RecordingState.RECORDING:
            self._paint_recording(painter)
        elif state == RecordingState.TRANSCRIBING:
            self._paint_transcribing(painter)
        elif state == RecordingState.CANCELLED:
            self._paint_cancelled(painter)
        elif state == RecordingState.ERROR:
            self._paint_error(painter)

    def _draw_folder(self, painter: QPainter, x: float, color: QColor) -> None:
        painter.setBrush(Qt.NoBrush)
        pen = QPen(color)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(x, self._CY - 5.0, 7.0, 4.0), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(x, self._CY - 2.0, 15.0, 9.0), 1.5, 1.5)

    def _pulse_dot(self, painter: QPainter, x: float, base: float, color: QColor) -> None:
        phase = 0.5 + 0.5 * math.cos(2 * math.pi * ((self._frame % 32) / 32.0))
        scale = 0.82 + 0.18 * phase
        alpha = int(255 * (0.5 + 0.5 * phase))
        size = base * scale
        tint = QColor(color)
        tint.setAlpha(alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(tint)
        painter.drawEllipse(QRectF(x + (base - size) / 2, self._CY - size / 2, size, size))

    def _paint_idle(self, painter: QPainter) -> None:
        self._draw_folder(painter, self._LEFT, QColor(MUTED_COLOR))
        record, dismiss = self._record_rect(), self._dismiss_rect()
        text_left, text_right = 40, record.left() - 8

        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(
            QRect(text_left, 11, text_right - text_left, 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            destination_display_name(self._dest_pill.name),
        )
        subline = i18n.t("state.ready")
        if self._hotkey_label:
            subline = f"{subline} · {self._hotkey_label}"
        painter.setPen(QColor(SUBTLE_COLOR))
        painter.setFont(self._font(11))
        painter.drawText(
            QRect(text_left, 31, text_right - text_left, 16),
            Qt.AlignVCenter | Qt.AlignLeft,
            subline,
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 92, 87, 36))
        painter.drawEllipse(record)
        painter.setBrush(QColor(COLOR_RECORDING))
        inner = 13
        painter.drawEllipse(
            record.center().x() - inner // 2 + 1, record.center().y() - inner // 2 + 1, inner, inner
        )
        painter.setPen(QColor(SUBTLE_COLOR))
        painter.setFont(self._font(15))
        painter.drawText(dismiss, Qt.AlignCenter, "×")

    def _paint_recording(self, painter: QPainter) -> None:
        self._pulse_dot(painter, self._LEFT, 11.0, QColor(COLOR_RECORDING))
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(14, bold=True))
        label = state_label(RecordingState.RECORDING)
        label_w = painter.fontMetrics().horizontalAdvance(label)
        label_x = self._LEFT + 11 + 10
        painter.drawText(
            QRect(label_x, 0, label_w + 4, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignLeft,
            label,
        )
        stop = self._stop_rect()
        tag_left = self._draw_mode_tag(painter, stop.left() - 10)
        leds_right = self._paint_chunk_leds(painter, tag_left - 8)
        self._paint_waveform(
            painter, QColor(COLOR_RECORDING), label_x + label_w + 12, leds_right - 8
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 92, 87, 41))
        painter.drawEllipse(stop)
        painter.setBrush(QColor(COLOR_RECORDING))
        square = 11.0
        painter.drawRoundedRect(
            QRectF(
                stop.center().x() - square / 2 + 1,
                stop.center().y() - square / 2 + 1,
                square,
                square,
            ),
            2,
            2,
        )

    def _draw_mode_tag(self, painter: QPainter, right_x: int) -> int:
        painter.setFont(self._font(11, bold=True))
        metrics = painter.fontMetrics()
        height, pad, gap = 20, 8, 6
        y = (INDICATOR_HEIGHT - height) // 2
        if self._mode == "meeting":
            text = i18n.t("state.tag.meeting")
            text_w = metrics.horizontalAdvance(text)
            tag_w = pad * 2 + 6 + gap + text_w
            left = right_x - tag_w
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(92, 147, 199, 51))
            painter.drawRoundedRect(QRectF(left, y, tag_w, height), 10, 10)
            painter.setBrush(QColor(COLOR_MEETING_DOT))
            painter.drawEllipse(QRectF(left + pad, self._CY - 3, 6, 6))
            painter.setPen(QColor(COLOR_MEETING_TEXT))
            painter.drawText(
                QRectF(left + pad + 6 + gap, y, text_w + 2, height),
                Qt.AlignVCenter | Qt.AlignLeft,
                text,
            )
            return int(left)
        glyph = "●" if self._mode == "ptt" else "↔"
        key = "state.tag.ptt" if self._mode == "ptt" else "state.tag.toggle"
        combined = f"{glyph} {i18n.t(key)}"
        text_w = metrics.horizontalAdvance(combined)
        tag_w = pad * 2 + text_w
        left = right_x - tag_w
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(QRectF(left, y, tag_w, height), 10, 10)
        painter.setPen(QColor(TAG_TEXT_COLOR))
        painter.drawText(
            QRectF(left + pad, y, text_w + 2, height),
            Qt.AlignVCenter | Qt.AlignLeft,
            combined,
        )
        return int(left)

    def _paint_chunk_leds(self, painter: QPainter, right_x: int) -> int:
        """Twee LCD-iconen (◇ stilte, ⏱ tijd); retourneert linker rand voor waveform."""

        enabled, vad_on, fixed_on = chunk_led_snapshot()
        if not enabled:
            return right_x

        painter.setFont(self._font(13, bold=True))
        metrics = painter.fontMetrics()
        vad_glyph = "◇"
        time_glyph = "⏱"
        gap = 5
        vad_w = metrics.horizontalAdvance(vad_glyph)
        time_w = metrics.horizontalAdvance(time_glyph)
        width = vad_w + gap + time_w
        left = right_x - width
        y = 0
        h = INDICATOR_HEIGHT

        painter.setPen(QColor(COLOR_CHUNK_LED_VAD if vad_on else COLOR_CHUNK_LED_IDLE))
        painter.drawText(
            QRect(int(left), y, vad_w + 2, h),
            Qt.AlignVCenter | Qt.AlignLeft,
            vad_glyph,
        )
        painter.setPen(QColor(COLOR_CHUNK_LED_FIXED if fixed_on else COLOR_CHUNK_LED_IDLE))
        painter.drawText(
            QRect(int(left + vad_w + gap), y, time_w + 2, h),
            Qt.AlignVCenter | Qt.AlignLeft,
            time_glyph,
        )
        return int(left)

    def _paint_waveform(
        self, painter: QPainter, color: QColor, x_left: float, x_right: float
    ) -> None:
        region = max(0.0, x_right - x_left)
        if region <= 0:
            return
        levels = snapshot_levels()
        padded = [0.0] * (NUM_BARS - len(levels)) + levels[-NUM_BARS:]
        slot = region / NUM_BARS
        bar_width = 2.0
        max_half = 10.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        for index, level in enumerate(padded):
            half = max(1.5, min(1.0, level * WAVEFORM_GAIN) * max_half)
            cx = x_left + slot * index + slot / 2
            painter.drawRoundedRect(
                QRectF(cx - bar_width / 2, self._CY - half, bar_width, half * 2), 1, 1
            )

    def _paint_transcribing(self, painter: QPainter) -> None:
        painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(COLOR_TRANSCRIBING))
        pen.setWidthF(2.0)
        painter.setPen(pen)
        diameter = 13.0
        arc = QRectF(self._LEFT, self._CY - diameter / 2, diameter, diameter)
        start = (self._frame * 12) % 360
        painter.drawArc(arc, int(-start * 16), int(300 * 16))

        x = self._LEFT + diameter + 10
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(14, bold=True))
        label = state_label(RecordingState.TRANSCRIBING)
        label_w = painter.fontMetrics().horizontalAdvance(label)
        painter.drawText(
            QRect(x, 0, label_w + 4, INDICATOR_HEIGHT), Qt.AlignVCenter | Qt.AlignLeft, label
        )
        x += label_w + 8

        percent = get_transcription_progress()
        if percent is not None:
            percent_text = f"{percent} %"
            painter.setPen(QColor(COLOR_TRANSCRIBING))
            percent_w = painter.fontMetrics().horizontalAdvance(percent_text)
            painter.drawText(
                QRect(x, 0, percent_w + 4, INDICATOR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignLeft,
                percent_text,
            )
            x += percent_w + 10
        self._paint_marching_dots(painter, x)
        self._draw_mode_tag(painter, INDICATOR_WIDTH - 16)

        if percent is not None:
            clip = QPainterPath()
            clip.addRoundedRect(
                QRectF(0.5, 0.5, INDICATOR_WIDTH - 1.0, INDICATOR_HEIGHT - 1.0),
                INDICATOR_HEIGHT / 2,
                INDICATOR_HEIGHT / 2,
            )
            painter.setClipPath(clip)
            thread = QColor(COLOR_TRANSCRIBING)
            thread.setAlphaF(0.85)
            painter.setPen(Qt.NoPen)
            painter.setBrush(thread)
            painter.drawRect(QRectF(0, INDICATOR_HEIGHT - 2, INDICATOR_WIDTH * percent / 100.0, 2))
            painter.setClipping(False)

    def _paint_marching_dots(self, painter: QPainter, x: float) -> None:
        active = (self._frame // 4) % 3
        painter.setPen(Qt.NoPen)
        for index in range(3):
            dot = QColor(COLOR_TRANSCRIBING)
            dot.setAlpha(255 if index == active else 90)
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(x + index * 7, self._CY - 2, 4, 4))

    def _paint_cancelled(self, painter: QPainter) -> None:
        painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(COLOR_CANCELLED))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.drawEllipse(QRectF(self._LEFT, self._CY - 6, 12, 12))
        painter.drawLine(
            QPointF(self._LEFT + 1, self._CY + 4), QPointF(self._LEFT + 11, self._CY - 4)
        )
        painter.setPen(QColor(MUTED_COLOR))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(
            QRect(self._LEFT + 12 + 11, 0, 180, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignLeft,
            state_label(RecordingState.CANCELLED),
        )
        painter.setPen(QColor("#6E757D"))
        painter.setFont(self._font(11))
        painter.drawText(
            QRect(0, 0, INDICATOR_WIDTH - 16, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignRight,
            i18n.t("state.cancelled_note"),
        )

    def _paint_error(self, painter: QPainter) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_ERROR))
        top = self._CY - 6
        triangle = QPainterPath()
        triangle.moveTo(self._LEFT + 7, top)
        triangle.lineTo(self._LEFT + 14, top + 12)
        triangle.lineTo(self._LEFT, top + 12)
        triangle.closeSubpath()
        painter.drawPath(triangle)
        painter.setPen(QColor(COLOR_ERROR_LABEL))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(
            QRect(self._LEFT + 14 + 10, 0, 180, INDICATOR_HEIGHT),
            Qt.AlignVCenter | Qt.AlignLeft,
            state_label(RecordingState.ERROR),
        )
        if self._hotkey_label:
            painter.setPen(QColor(SUBTLE_COLOR))
            painter.setFont(self._font(11))
            painter.drawText(
                QRect(0, 0, INDICATOR_WIDTH - 16, INDICATOR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignRight,
                self._hotkey_label,
            )
