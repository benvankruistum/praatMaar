"""Qt implementation of praatMaar's always-on-top recording status pill."""

from __future__ import annotations

import math
import time
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
    COLOR_PREPARING,
    COLOR_RECORDING,
    COLOR_RECORDING_DOT,
    COLOR_TRANSCRIBING,
    COLOR_TRANSCRIBING_TEXT,
    ERROR_DURATION_MS,
    INDICATOR_HEIGHT,
    INDICATOR_WIDTH,
    MUTED_COLOR,
    NUM_BARS,
    PILL_BG,
    PILL_BG_ERROR,
    POLL_INTERVAL_IDLE_MS,
    POLL_INTERVAL_MS,
    POSITION_LAST,
    PROGRESS_BAR_HEIGHT,
    PROGRESS_TRACK_COLOR,
    READY_CUE_DURATION_MS,
    STOP_BUTTON_SIZE,
    SUBTLE_COLOR,
    TAG_TEXT_COLOR,
    TEXT_COLOR,
    WAVEFORM_BAR_MAX_HEIGHT,
    WAVEFORM_BAR_WIDTH,
    WAVEFORM_GAIN,
    WINDOW_ALPHA,
    DestinationPillModel,
    RecordingState,
    chunk_led_snapshot,
    clamp_indicator_xy,
    destination_display_name,
    destination_path_label,
    drain_status_queue,
    elapsed_label,
    get_transcription_progress,
    hotkey_chips,
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
        on_retry: Any | None = None,
    ) -> None:
        ensure_app()
        super().__init__()
        apply_hud_window_flags(self)
        self.setFixedSize(INDICATOR_WIDTH, INDICATOR_HEIGHT)
        self.setWindowOpacity(WINDOW_ALPHA)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._state = RecordingState.IDLE
        self._mode = "toggle"
        self._status_hint = ""
        self._ready_cue_active = False
        self._frame = 0
        self._position = normalize_indicator_position(position)
        self._xy = xy
        self._on_moved = on_moved
        self._control_press_cb = on_control_press
        self._control_release_cb = on_control_release
        self.on_context_menu = on_context_menu
        self._retry_cb = on_retry
        self.state_listener: Any | None = None
        self._drag_offset: QPoint | None = None
        self._drag_moved = False
        self._control_held = False
        self._dest_pill = DestinationPillModel()
        self._stop_requested = False
        self._hotkey_label: str | None = None
        self._recording_started_at: float | None = None
        self._destination_path: str | None = None
        self._hide_remaining_ms: int | None = None

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
        if self._ready_cue_active or self._dest_pill.idle_visible:
            self._show_window()
        else:
            self._hide_window()

    def _apply_state(self, state: RecordingState, mode: str, hint: str = "") -> None:
        self._ready_cue_active = False
        self._mode = mode
        self._state = state
        self._status_hint = (
            hint
            if state
            in (
                RecordingState.ERROR,
                RecordingState.PREPARING,
            )
            else ""
        )
        self._notify_listener(state, mode)
        self._hide_timer.stop()

        if state == RecordingState.RECORDING:
            self._dest_pill.on_recording_started()
            if self._recording_started_at is None:
                self._recording_started_at = time.monotonic()
        else:
            self._recording_started_at = None

        if state == RecordingState.IDLE:
            self._apply_idle_visibility()
        else:
            self._show_window()
            if state == RecordingState.CANCELLED:
                self._hide_timer.start(CANCELLED_DURATION_MS)
            elif state == RecordingState.ERROR:
                self._hide_timer.start(ERROR_DURATION_MS)
        self._sync_timer_interval()
        self.update()

    def _transient_expired(self) -> None:
        self._ready_cue_active = False
        self._state = RecordingState.IDLE
        self._status_hint = ""
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

    def set_destination(self, name: str | None, path: str | None = None) -> None:
        self._destination_path = (path or "").strip() or None
        self._dest_pill.set_destination(name)
        self._sync_destination_tooltip()

    def _sync_destination_tooltip(self) -> None:
        """Volledig pad als tooltip.

        Bij 340 px blijft er na de toets-chips en de twee knoppen ~129 px over
        voor tekst — genoeg voor de bestemmingsnaam, niet voor naam én pad. De
        tooltip geeft het volle pad zonder ruimte te kosten.
        """

        name = self._dest_pill.name or ""
        path = self._destination_path or ""
        if name and path:
            self.setToolTip(f"{name}\n{path}")
        else:
            self.setToolTip(path or name)
        if self._state == RecordingState.IDLE:
            self._apply_idle_visibility()
            self.update()

    def set_hotkey_label(self, text: str | None) -> None:
        """Set the shortcut shown in the idle subline (e.g. ``Ctrl + Space``)."""
        self._hotkey_label = (text or "").strip() or None
        if self.isVisible():
            self.update()

    def show_ready_cue(self, duration_ms: int = READY_CUE_DURATION_MS) -> None:
        """Korte non-activating gereed-pill na splash (FR-UX-05 B)."""

        self._ready_cue_active = True
        self._state = RecordingState.IDLE
        self._status_hint = ""
        self._hide_timer.stop()
        self._show_window()
        self._hide_timer.start(max(0, int(duration_ms)))
        self.update()

    _ANIMATED_STATES = (
        RecordingState.PREPARING,
        RecordingState.RECORDING,
        RecordingState.TRANSCRIBING,
    )

    def _is_animated(self) -> bool:
        """True zolang er iets beweegt dat een repaint per frame rechtvaardigt.

        Idle, Geannuleerd en Mislukt staan stil: daar is 20 repaints per seconde
        pure verspilling op een altijd-zichtbare HUD. Krijgt de ready-cue in een
        latere slice zijn eenmalige ring, dan hoort die hier ook bij.
        """

        return self._state in self._ANIMATED_STATES

    def _sync_timer_interval(self) -> None:
        if self._timer is None:
            return
        wanted = POLL_INTERVAL_MS if self._is_animated() else POLL_INTERVAL_IDLE_MS
        if self._timer.interval() != wanted:
            self._timer.setInterval(wanted)

    def _tick(self) -> None:
        if self._stop_requested:
            self._stop()
            return
        changed = False
        for state, mode, hint in drain_status_queue():
            self._apply_state(state, mode, hint)
            changed = True
        self._frame += 1
        # Alleen schilderen als er iets beweegt of net iets veranderd is;
        # _apply_state heeft bij een wissel zelf al update() aangeroepen.
        if self.isVisible() and self._is_animated() and not changed:
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

    def enterEvent(self, _event: Any) -> None:  # noqa: N802
        """Cursor boven de pill: auto-hide pauzeren (canvas 07).

        Anders verdwijnt een foutmelding onder je muis weg terwijl je hem leest
        of naar de actieknop beweegt.
        """

        if self._hide_timer.isActive():
            self._hide_remaining_ms = self._hide_timer.remainingTime()
            self._hide_timer.stop()
        super().enterEvent(_event)

    def leaveEvent(self, _event: Any) -> None:  # noqa: N802
        remaining = self._hide_remaining_ms
        self._hide_remaining_ms = None
        if remaining is not None and self._state in (
            RecordingState.ERROR,
            RecordingState.CANCELLED,
        ):
            self._hide_timer.start(max(0, remaining))
        super().leaveEvent(_event)

    def _dismiss_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - _RIGHT_PAD - _BTN, _BTN_Y, _BTN, _BTN)

    def _record_rect(self) -> QRect:
        return QRect(INDICATOR_WIDTH - _RIGHT_PAD - _BTN * 2 - 10, _BTN_Y, _BTN, _BTN)

    def _stop_rect(self) -> QRect:
        size = STOP_BUTTON_SIZE
        return QRect(
            INDICATOR_WIDTH - _RIGHT_PAD - size,
            (INDICATOR_HEIGHT - size) // 2,
            size,
            size,
        )

    def _retry_rect(self) -> QRect | None:
        """Actieknop bij Mislukt; None in elke andere state (canvas 07)."""

        if self._state != RecordingState.ERROR:
            return None
        width, height = 68, 32
        return QRect(
            INDICATOR_WIDTH - _RIGHT_PAD - width,
            (INDICATOR_HEIGHT - height) // 2,
            width,
            height,
        )

    def _progress_bar_rect(self) -> QRect | None:
        """Balk in de tekstkolom; None als er niets te tonen valt.

        Alleen tijdens TRANSCRIBEREN én met een bekend percentage: bij
        onbekende duur blijven de marching dots het indeterminate-signaal.
        """

        if self._state != RecordingState.TRANSCRIBING:
            return None
        if get_transcription_progress() is None:
            return None
        left = self._LEFT + 13 + 10
        # Zelfde rechtergrens als de tekstkolom in _paint_transcribing: tag
        # (~64 px) + marching dots (18 px) + tussenruimte.
        right = INDICATOR_WIDTH - 16 - 64 - 8 - 18 - 10
        width = right - left
        if width <= 0:
            return None
        return QRect(left, 36, width, PROGRESS_BAR_HEIGHT)

    @staticmethod
    def _progress_fill_width(rect: QRect, percent: int) -> float:
        ratio = max(0, min(100, int(percent))) / 100.0
        return rect.width() * ratio

    def _elapsed_seconds(self) -> int:
        """Looptijd van de huidige opname; 0 zodra er niet opgenomen wordt."""

        started = self._recording_started_at
        if started is None or self._state != RecordingState.RECORDING:
            return 0
        return max(0, int(time.monotonic() - started))

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

        if self._state == RecordingState.ERROR:
            retry = self._retry_rect()
            if retry is not None and retry.contains(event.position().toPoint()):
                self._invoke_callback(self._retry_cb)
                event.accept()
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
        """1 px capsulerand; tint volgt de state-kleur (canvas 1a)."""

        state = self._state
        tinted = {
            RecordingState.RECORDING: (COLOR_RECORDING, 90),
            RecordingState.PREPARING: (COLOR_PREPARING, 51),
            RecordingState.TRANSCRIBING: (COLOR_TRANSCRIBING, 61),
            RecordingState.ERROR: (COLOR_ERROR, 90),
        }
        if state in tinted:
            token, alpha = tinted[state]
            color = QColor(token)
            color.setAlpha(alpha)
            return color
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
            if self._ready_cue_active or self._dest_pill.idle_visible:
                self._paint_idle(painter)
        elif state == RecordingState.PREPARING:
            self._paint_preparing(painter)
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

    def _slow_pulse_dot(self, painter: QPainter, x: float, base: float, color: QColor) -> None:
        """Gedempte, trage pulse — onderscheidbaar van de opname-dot."""

        phase = 0.5 + 0.5 * math.cos(2 * math.pi * ((self._frame % 64) / 64.0))
        scale = 0.88 + 0.12 * phase
        alpha = int(255 * (0.35 + 0.35 * phase))
        size = base * scale
        tint = QColor(color)
        tint.setAlpha(alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(tint)
        painter.drawEllipse(QRectF(x + (base - size) / 2, self._CY - size / 2, size, size))

    def _paint_idle(self, painter: QPainter) -> None:
        self._draw_folder(painter, self._LEFT, QColor(MUTED_COLOR))
        record, dismiss = self._record_rect(), self._dismiss_rect()
        text_left = 40

        # Toets-chips rechts van de tekst: die reserveren hun breedte eerst,
        # zodat de tekstkolom weet waar hij mag eindigen (canvas 01).
        chips_left = self._draw_hotkey_chips(painter, record.left() - 10)
        text_right = chips_left - 10

        # Canvas-regelorde: status boven, bestemming eronder.
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(
            QRect(text_left, 11, max(0, text_right - text_left), 20),
            Qt.AlignVCenter | Qt.AlignLeft,
            i18n.t("state.ready"),
        )

        # Regel 2: naam én pad — je ziet wát actief is en wáár het landt.
        name = destination_display_name(self._dest_pill.name)
        painter.setPen(QColor(SUBTLE_COLOR))
        painter.setFont(self._font(11))
        available = max(0, text_right - text_left)
        metrics = painter.fontMetrics()
        subline = name
        path_label = destination_path_label(self._destination_path)
        if path_label and path_label != name:
            if not name:
                subline = metrics.elidedText(path_label, Qt.TextElideMode.ElideMiddle, available)
            else:
                # Naam blijft heel; alleen het pad krimpt (midden-ellipsis) tot
                # wat er overblijft. Onder ~40 px is een padrestje onleesbaar,
                # dan valt het pad weg i.p.v. "O…s" te tonen.
                separator = " · "
                room = available - metrics.horizontalAdvance(name + separator)
                if room >= 40:
                    subline = (
                        name
                        + separator
                        + metrics.elidedText(path_label, Qt.TextElideMode.ElideMiddle, room)
                    )
        painter.drawText(
            QRect(text_left, 31, available, 16),
            Qt.AlignVCenter | Qt.AlignLeft,
            subline,
        )

        painter.setPen(Qt.NoPen)
        halo = QColor(COLOR_RECORDING)
        halo.setAlpha(36)
        painter.setBrush(halo)
        painter.drawEllipse(record)
        painter.setBrush(QColor(COLOR_RECORDING))
        inner = 13
        painter.drawEllipse(
            record.center().x() - inner // 2 + 1, record.center().y() - inner // 2 + 1, inner, inner
        )
        painter.setPen(QColor(SUBTLE_COLOR))
        painter.setFont(self._font(15))
        painter.drawText(dismiss, Qt.AlignCenter, "×")

    def _paint_preparing(self, painter: QPainter) -> None:
        """Warm-up: geen waveform; trage muted pulse ≠ Opname."""

        self._slow_pulse_dot(painter, self._LEFT, 10.0, QColor(COLOR_PREPARING))
        tag_left = self._draw_mode_tag(painter, INDICATOR_WIDTH - 16)
        text_left = int(self._LEFT + 10 + 10)
        text_right = tag_left - 8
        width = max(0, text_right - text_left)

        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(14, bold=True))
        label = state_label(RecordingState.PREPARING)
        if self._status_hint:
            painter.drawText(
                QRect(text_left, 11, width, 20),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )
            painter.setPen(QColor(SUBTLE_COLOR))
            painter.setFont(self._font(11))
            painter.drawText(
                QRect(text_left, 31, width, 16),
                Qt.AlignVCenter | Qt.AlignLeft,
                self._status_hint,
            )
        else:
            painter.drawText(
                QRect(text_left, 0, width, INDICATOR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )

    def _paint_recording(self, painter: QPainter) -> None:
        self._pulse_dot(painter, self._LEFT, 11.0, QColor(COLOR_RECORDING_DOT))
        label = state_label(RecordingState.RECORDING)
        label_x = self._LEFT + 11 + 10

        # Label + looptijd als twee regels (canvas 04). De looptijd staat in de
        # state-kleur-neutrale subtint, zodat de rode stip het enige "live"-
        # signaal blijft.
        painter.setFont(self._font(13, bold=True))
        label_w = painter.fontMetrics().horizontalAdvance(label)
        elapsed = elapsed_label(self._elapsed_seconds())
        painter.setFont(self._font(11))
        elapsed_w = painter.fontMetrics().horizontalAdvance(elapsed)
        text_w = max(label_w, elapsed_w)

        painter.setPen(QColor(COLOR_RECORDING_DOT))
        painter.setFont(self._font(13, bold=True))
        painter.drawText(
            QRect(label_x, 12, text_w + 4, 18),
            Qt.AlignVCenter | Qt.AlignLeft,
            label,
        )
        painter.setPen(QColor(SUBTLE_COLOR))
        painter.setFont(self._font(11))
        painter.drawText(
            QRect(label_x, 30, text_w + 4, 16),
            Qt.AlignVCenter | Qt.AlignLeft,
            elapsed,
        )
        label_w = text_w
        stop = self._stop_rect()
        tag_left = self._draw_mode_tag(painter, stop.left() - 10)
        leds_right = self._paint_chunk_leds(painter, tag_left - 8)
        self._paint_waveform(
            painter, QColor(COLOR_RECORDING), label_x + label_w + 12, leds_right - 8
        )

        # Canvas 04/10: gevulde knop 36×36 radius 12 met wit vierkant 12×12 —
        # leest als knop, niet als vlak.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_RECORDING))
        painter.drawRoundedRect(QRectF(stop), 12, 12)
        painter.setBrush(QColor("#FFFFFF"))
        square = 12.0
        painter.drawRoundedRect(
            QRectF(
                stop.center().x() - square / 2 + 1,
                stop.center().y() - square / 2 + 1,
                square,
                square,
            ),
            3,
            3,
        )

    def _draw_hotkey_chips(self, painter: QPainter, right_x: int) -> int:
        """Sneltoets als omrande toetsjes; retourneert de linkerrand.

        Chips lezen op 11 px sneller dan "Ctrl+Alt+R" als doorlopende tekst
        (canvas 01). Zonder sneltoets verandert er niets aan de layout.
        """

        chips = hotkey_chips(self._hotkey_label)
        if not chips:
            return right_x

        painter.setFont(self._font(10))
        metrics = painter.fontMetrics()
        pad_x, gap, height = 5, 4, 18
        widths = [metrics.horizontalAdvance(chip) + pad_x * 2 for chip in chips]
        total = sum(widths) + gap * (len(chips) - 1)
        left = right_x - total
        y = (INDICATOR_HEIGHT - height) / 2.0

        x = float(left)
        for chip, width in zip(chips, widths, strict=True):
            painter.setPen(QPen(QColor(255, 255, 255, 46)))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(x, y, width, height), 4, 4)
            painter.setPen(QColor(SUBTLE_COLOR))
            painter.drawText(QRectF(x, y, width, height), Qt.AlignCenter, chip)
            x += width + gap
        return int(left)

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
        bar_width = WAVEFORM_BAR_WIDTH
        max_half = WAVEFORM_BAR_MAX_HEIGHT / 2.0
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

        percent = get_transcription_progress()
        bar = self._progress_bar_rect()

        # Rechts eerst: tag en dots bepalen waar de tekstkolom mag eindigen.
        tag_left = self._draw_mode_tag(painter, INDICATOR_WIDTH - 16)
        dots_left = tag_left - 8 - 18
        self._paint_marching_dots(painter, dots_left)

        column_left = self._LEFT + diameter + 10
        column_right = dots_left - 10
        label = state_label(RecordingState.TRANSCRIBING)

        # Met balk staan label en percentage op één regel bóven de balk; zonder
        # balk (onbekende duur) blijft de regel verticaal gecentreerd.
        row_y, row_h = (14, 18) if bar is not None else (0, INDICATOR_HEIGHT)
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(self._font(13, bold=True))
        painter.drawText(
            QRect(column_left, row_y, max(0, column_right - column_left), row_h),
            Qt.AlignVCenter | Qt.AlignLeft,
            label,
        )
        if percent is not None:
            painter.setPen(QColor(COLOR_TRANSCRIBING_TEXT))
            painter.setFont(self._font(12, bold=True))
            painter.drawText(
                QRect(column_left, row_y, max(0, column_right - column_left), row_h),
                Qt.AlignVCenter | Qt.AlignRight,
                f"{percent} %",
            )

        bar = self._progress_bar_rect()
        if bar is not None and percent is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PROGRESS_TRACK_COLOR))
            radius = PROGRESS_BAR_HEIGHT / 2.0
            painter.drawRoundedRect(QRectF(bar), radius, radius)
            filled = self._progress_fill_width(bar, percent)
            if filled > 0:
                painter.setBrush(QColor(COLOR_TRANSCRIBING))
                painter.drawRoundedRect(
                    QRectF(bar.left(), bar.top(), filled, bar.height()), radius, radius
                )

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

        text_left = int(self._LEFT + 14 + 10)
        retry = self._retry_rect()
        text_right = (retry.left() - 10) if retry is not None else (INDICATOR_WIDTH - 16)
        text_width = max(0, text_right - text_left)

        painter.setPen(QColor(COLOR_ERROR_LABEL))
        painter.setFont(self._font(13, bold=True))
        label = state_label(RecordingState.ERROR)
        if self._status_hint:
            painter.drawText(
                QRect(text_left, 11, text_width, 20),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )
            painter.setPen(QColor(MUTED_COLOR))
            painter.setFont(self._font(11))
            metrics = painter.fontMetrics()
            painter.drawText(
                QRect(text_left, 31, text_width, 16),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(self._status_hint, Qt.TextElideMode.ElideRight, text_width),
            )
        else:
            painter.drawText(
                QRect(text_left, 0, text_width, INDICATOR_HEIGHT),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )

        if retry is not None:
            # Gevulde amber knop met donkere tekst: de enige actie in deze
            # state, dus hij mag de aandacht trekken.
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(COLOR_ERROR))
            painter.drawRoundedRect(QRectF(retry), 10, 10)
            painter.setPen(QColor("#151719"))
            painter.setFont(self._font(11, bold=True))
            painter.drawText(retry, Qt.AlignCenter, i18n.t("state.error_retry_action"))
