"""Compact Qt Meeting Buddy heads-up display; deliberately has no transcript view."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from indicator._contract import (
    COLOR_MEETING_TEXT,
    COLOR_RECORDING,
    NUM_BARS,
    PILL_BG,
    SUBTLE_COLOR,
    TEXT_COLOR,
    snapshot_loopback_levels,
    snapshot_mic_levels,
)
from ui.app import ensure_app
from ui.overlay_flags import apply_hud_window_flags
from ui.theme import TOKENS

from .hints import HintType
from .state import Hint, HintStatus, MeetingState, Question, QuestionStatus, Topic, TopicStatus
from .topic_ladder import is_at_least_sequential


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as a stable ``HH:MM:SS`` timer."""
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


_TOPIC_MARK = {
    TopicStatus.OPEN: "○",
    TopicStatus.TREATED: "◐",
    TopicStatus.SEQUENTIAL: "●",
    TopicStatus.CONFIRMED: "✓",
}


def format_topic_line(topic: Topic) -> str:
    """Compact agenda line with ladder mark plus title."""
    return f"{_TOPIC_MARK.get(topic.status, '○')} {topic.title}"


def topic_line_color(topic: Topic) -> str:
    if topic.status == TopicStatus.CONFIRMED:
        return "#8A94A0"
    if is_at_least_sequential(topic.status):
        return "#0A4C86"
    if topic.status == TopicStatus.TREATED:
        return "#0F6CBD"
    return "#1B1F24"


def pick_emphasis(hints: Sequence[Hint]) -> str | None:
    """Return the id of the highest-priority active hint."""
    active = [hint for hint in hints if hint.status == HintStatus.ACTIVE]
    return (
        max(active, key=lambda hint: (hint.priority, hint.confidence, hint.id)).id
        if active
        else None
    )


def _topics_done(topics: Sequence[Topic]) -> int:
    return sum(1 for t in topics if t.status in (TopicStatus.SEQUENTIAL, TopicStatus.CONFIRMED))


def summary_points(text: str, *, limit: int = 3) -> list[str]:
    """Split a live summary into up to ``limit`` separate points (canvas 03).

    Prefers explicit lines (stripping bullet markers); falls back to sentence
    splitting for a single paragraph.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    lines = [
        re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        for line in cleaned.splitlines()
        if line.strip()
    ]
    if len(lines) > 1:
        return lines[:limit]
    base = lines[0] if lines else cleaned
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", base) if part.strip()]
    return sentences[:limit] if sentences else [base]


class _StatusDot(QWidget):
    """Agenda-ladder mark: shape carries meaning (ring/half/full/check)."""

    def __init__(self, status: TopicStatus) -> None:
        super().__init__()
        self._status = status
        self.setFixedSize(14, 14)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.75, 0.75, 12.5, 12.5)
        accent = QColor(TOKENS["accent"])
        if self._status == TopicStatus.CONFIRMED:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TOKENS["ok"]))
            painter.drawEllipse(rect)
            painter.setPen(QColor("white"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "✓")
        elif self._status == TopicStatus.SEQUENTIAL:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(rect)
        elif self._status == TopicStatus.TREATED:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawPie(rect, 90 * 16, 180 * 16)
            pen = QPen(accent)
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)
        else:
            pen = QPen(QColor(TOKENS["icon_muted"]))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)


class _HudWindow(QWidget):
    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()


class _SourceWaveforms(QWidget):
    """Two compact bar rows: microphone vs meeting (loopback) levels."""

    _DISPLAY_GAIN = 14.0
    _BARS = NUM_BARS

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("mbSourceLevels")
        self.setMinimumHeight(78)
        self._loopback_active: bool | None = None
        self._loopback_requested = False
        self._warn = QLabel()
        self._warn.setObjectName("mbLevelsWarn")
        self._warn.setWordWrap(True)
        self._warn.setStyleSheet(f"color: {TOKENS['amber_text']}; font-size: 11px;")
        self._warn.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 8)
        layout.setSpacing(6)
        self._canvas = _SourceWaveformCanvas(display_gain=self._DISPLAY_GAIN, bars=self._BARS)
        layout.addWidget(self._canvas)
        layout.addWidget(self._warn)

    def set_loopback_state(self, *, loopback_active: bool | None, loopback_requested: bool) -> None:
        self._loopback_active = loopback_active
        self._loopback_requested = loopback_requested
        self._canvas.set_loopback_live(loopback_active is True)
        if loopback_requested and loopback_active is False:
            self._warn.setText(
                i18n.t("modules.meeting_buddy.overlay.recording.mic_only_unavailable")
            )
            self._warn.show()
        elif not loopback_requested:
            self._warn.setText(i18n.t("modules.meeting_buddy.overlay.recording.mic_only"))
            self._warn.show()
        else:
            self._warn.hide()

    def refresh(self) -> None:
        self._canvas.refresh()


class _SourceWaveformCanvas(QWidget):
    def __init__(self, *, display_gain: float, bars: int) -> None:
        super().__init__()
        self.setFixedHeight(52)
        self._display_gain = display_gain
        self._bars = bars
        self._loopback_live = False
        self._mic: list[float] = []
        self._loop: list[float] = []

    def set_loopback_live(self, live: bool) -> None:
        self._loopback_live = live

    def refresh(self) -> None:
        self._mic = snapshot_mic_levels()
        # Always snapshot meeting levels when the stream exists or recently did;
        # empty deque → flat bars (honest “geen signaal”).
        self._loop = snapshot_loopback_levels()
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        row_h = self.height() / 2
        self._paint_row(
            painter,
            y=0,
            height=row_h,
            label=i18n.t("modules.meeting_buddy.overlay.levels.mic"),
            levels=self._mic,
            color=QColor(COLOR_RECORDING),
            muted=False,
        )
        meeting_color = QColor("#3D7AB5") if self._loopback_live else QColor(TOKENS["muted_soft"])
        self._paint_row(
            painter,
            y=row_h,
            height=row_h,
            label=i18n.t("modules.meeting_buddy.overlay.levels.meeting"),
            levels=self._loop if self._loopback_live else [],
            color=meeting_color,
            muted=not self._loopback_live,
        )

    def _paint_row(
        self,
        painter: QPainter,
        *,
        y: float,
        height: float,
        label: str,
        levels: list[float],
        color: QColor,
        muted: bool,
    ) -> None:
        label_w = 72
        painter.setPen(QColor(TOKENS["muted"] if muted else TOKENS["text_secondary"]))
        painter.drawText(
            QRectF(0, y, label_w, height),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            label,
        )
        x_left = label_w + 8
        x_right = float(self.width()) - 2
        region = max(0.0, x_right - x_left)
        if region <= 0:
            return
        # Track behind bars for readability.
        track = QColor(TOKENS["border"])
        track.setAlpha(90)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        track_h = max(6.0, height - 8)
        painter.drawRoundedRect(QRectF(x_left, y + (height - track_h) / 2, region, track_h), 4, 4)

        padded = [0.0] * (self._bars - len(levels)) + levels[-self._bars :]
        slot = region / self._bars
        bar_width = max(2.5, slot * 0.55)
        max_half = max(3.0, track_h / 2 - 1.5)
        cy = y + height / 2
        bar_color = QColor(color)
        if muted:
            bar_color.setAlpha(90)
        painter.setBrush(bar_color)
        for index, level in enumerate(padded):
            half = max(1.5, min(1.0, level * self._display_gain) * max_half)
            cx = x_left + slot * index + slot / 2
            painter.drawRoundedRect(
                QRectF(cx - bar_width / 2, cy - half, bar_width, half * 2), 1.5, 1.5
            )


class _DragHeader(QFrame):
    """Frameless HUD title bar: drag moves ``window`` (no ``startSystemMove``)."""

    def __init__(self, window: QWidget) -> None:
        super().__init__()
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("mbHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._window.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class _MiniPill(QWidget):
    """Minimized overlay: dark capsule (family of the dicteer-pill #2a)."""

    def __init__(self, on_expand: Callable[[], None]) -> None:
        super().__init__()
        apply_hud_window_flags(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(230, 44)
        self._drag_offset: QPoint | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 6, 0)
        row.setSpacing(7)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {COLOR_RECORDING}; font-size: 10px;")
        self._timer = QLabel("00:00:00")
        self._timer.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; font-family: {TOKENS['mono']};"
        )
        self._count = QLabel("")
        self._count.setStyleSheet(
            f"color: {SUBTLE_COLOR}; font-size: 12px; font-family: {TOKENS['mono']};"
        )
        expand = QPushButton("▴")
        expand.setCursor(Qt.CursorShape.PointingHandCursor)
        expand.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {SUBTLE_COLOR};"
            " font-size: 11px; min-width: 20px; }"
        )
        expand.clicked.connect(on_expand)
        for label in (self._dot, self._timer, self._count):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(self._dot)
        row.addWidget(self._timer)
        row.addWidget(self._count)
        row.addStretch(1)
        self._tag = QLabel(i18n.t("state.tag.meeting"))
        self._tag.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._tag.setStyleSheet(
            f"color: {COLOR_MEETING_TEXT}; background: rgba(92,147,199,0.20);"
            " border-radius: 10px; padding: 2px 7px; font-size: 10px; font-weight: 600;"
        )
        row.addWidget(self._tag)
        row.addWidget(expand)

    def set_state(self, timer: str, count: str) -> None:
        self._timer.setText(timer)
        self._count.setText(count)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PILL_BG))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 22, 22)


class MeetingBuddyOverlay:
    """Small always-on-top status and hints window."""

    def __init__(
        self,
        *,
        elapsed_seconds: Callable[[], float],
        on_dismiss: Callable[[str], None],
        on_confirm: Callable[[str], None],
        on_reconnect: Callable[[], None],
        on_stop: Callable[[], None] | None = None,
        parent: Any = None,
    ) -> None:
        ensure_app()
        self._elapsed_seconds = elapsed_seconds
        self._on_dismiss = on_dismiss
        self._on_confirm = on_confirm
        self._on_reconnect = on_reconnect
        self._shown_once = False
        self._capture_status: object = None
        self._pulse_on = False
        self._hint_cards: dict[str, QFrame] = {}
        self._topic_total = 0
        self._topic_done = 0
        self._mini: _MiniPill | None = None

        self.window = _HudWindow(parent if isinstance(parent, QWidget) else None)
        apply_hud_window_flags(self.window)
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.window.setWindowTitle(i18n.t("modules.meeting_buddy.overlay.title"))
        self.window.setMinimumWidth(360)

        shell = QVBoxLayout(self.window)
        shell.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("mbCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shell.addWidget(card)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- header bar ---
        header = _DragHeader(self.window)
        head = QHBoxLayout(header)
        head.setContentsMargins(12, 9, 10, 9)
        head.setSpacing(8)
        title = QLabel(i18n.t("modules.meeting_buddy.overlay.title"))
        title.setObjectName("mbHeaderTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        head.addWidget(title)
        head.addStretch(1)
        minimize = QPushButton("—")
        minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        minimize.setStyleSheet(self._icon_btn_qss(TOKENS["muted"]))
        minimize.clicked.connect(self.minimize)
        head.addWidget(minimize)
        if on_stop is not None:
            stop = QPushButton("■")
            stop.setCursor(Qt.CursorShape.PointingHandCursor)
            stop.setStyleSheet(self._icon_btn_qss(TOKENS["danger"], size=9))
            stop.clicked.connect(on_stop)
            head.addWidget(stop)
        outer.addWidget(header)

        # --- status row ---
        status_row = QHBoxLayout()
        status_row.setContentsMargins(12, 10, 12, 10)
        status_row.setSpacing(9)
        self._listening_dot = QLabel("●")
        self._listening_dot.setStyleSheet(f"color: {TOKENS['muted_soft']}; font-size: 11px;")
        self._listening = QLabel()
        self._listening.setObjectName("overlayStatus")
        self._timer_label = QLabel("00:00:00")
        self._timer_label.setObjectName("overlayTimer")
        status_row.addWidget(self._listening_dot)
        status_row.addWidget(self._listening)
        status_row.addStretch(1)
        status_row.addWidget(self._timer_label)
        outer.addLayout(status_row)

        self._source_levels = _SourceWaveforms()
        self._source_levels.hide()
        outer.addWidget(self._source_levels)

        # --- banner host ---
        self._banner_host = QWidget()
        banner_layout = QVBoxLayout(self._banner_host)
        banner_layout.setContentsMargins(12, 0, 12, 10)
        banner_layout.setSpacing(0)
        outer.addWidget(self._banner_host)

        content = QWidget()
        content_row = QHBoxLayout(content)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Left status column: agenda, questions, hints.
        self._left_col = QWidget()
        left = QVBoxLayout(self._left_col)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        self._topics, self._topics_body, self._topics_count = self._section(
            "modules.meeting_buddy.overlay.agenda", left
        )
        self._questions, self._questions_body, self._questions_count = self._section(
            "modules.meeting_buddy.overlay.questions", left
        )
        self._hints, self._hints_body, self._hints_count = self._section(
            "modules.meeting_buddy.overlay.hints", left
        )
        content_row.addWidget(self._left_col, 1)

        # Right summary column (canvas 03): shown only when live summary is on.
        self._summary_text = ""
        self._summary_col = self._build_summary_column()
        content_row.addWidget(self._summary_col)
        outer.addWidget(content)

        # --- footer ---
        footer = QFrame()
        footer.setObjectName("mbFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(12, 7, 12, 7)
        foot.setSpacing(8)
        self._footer_label = QLabel()
        self._footer_label.setObjectName("overlayFooterText")
        foot.addWidget(self._footer_label)
        foot.addStretch(1)
        local = QLabel(i18n.t("modules.meeting_buddy.overlay.local"))
        local.setObjectName("overlayFooterText")
        foot.addWidget(local)
        outer.addWidget(footer)

        self._timer = QTimer(self.window)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._levels_timer = QTimer(self.window)
        self._levels_timer.timeout.connect(self._source_levels.refresh)
        self._levels_timer.start(50)
        self._tick()

    @staticmethod
    def _icon_btn_qss(color: str, *, size: int = 13) -> str:
        return (
            f"QPushButton {{ background: transparent; border: none; color: {color};"
            f" font-size: {size}px; min-width: 24px; min-height: 24px; border-radius: 4px; }}"
            f" QPushButton:hover {{ background: {TOKENS['hover']}; }}"
        )

    def _section(self, key: str, target: QVBoxLayout) -> tuple[QWidget, QVBoxLayout, QLabel]:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(7)
        head = QHBoxLayout()
        head.setSpacing(8)
        heading = QLabel(i18n.t(key).upper())
        heading.setObjectName("overlaySection")
        count = QLabel("")
        count.setObjectName("overlayFooterText")
        head.addWidget(heading)
        head.addStretch(1)
        head.addWidget(count)
        layout.addLayout(head)
        body_layout = QVBoxLayout()
        body_layout.setSpacing(6)
        layout.addLayout(body_layout)
        target.addWidget(section)
        section.hide()
        return section, body_layout, count

    def _build_summary_column(self) -> QWidget:
        column = QFrame()
        column.setObjectName("summaryCol")
        column.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        column.setFixedWidth(320)
        col = QVBoxLayout(column)
        col.setContentsMargins(14, 10, 14, 12)
        col.setSpacing(9)
        head = QHBoxLayout()
        head.setSpacing(8)
        heading = QLabel(i18n.t("modules.meeting_buddy.overlay.summary").upper())
        heading.setObjectName("overlaySection")
        self._summary_time = QLabel("")
        self._summary_time.setObjectName("overlayFooterText")
        head.addWidget(heading)
        head.addStretch(1)
        head.addWidget(self._summary_time)
        col.addLayout(head)
        self._summary_bullets = QVBoxLayout()
        self._summary_bullets.setSpacing(9)
        col.addLayout(self._summary_bullets)
        col.addStretch(1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        source = QLabel(i18n.t("modules.meeting_buddy.overlay.summary_source"))
        source.setObjectName("overlayFooterText")
        copy = QLabel(i18n.t("modules.meeting_buddy.overlay.summary_copy"))
        copy.setObjectName("summaryCopy")
        copy.setCursor(Qt.CursorShape.PointingHandCursor)
        copy.mousePressEvent = lambda _e: self._copy_summary()  # type: ignore[method-assign]
        footer.addWidget(source)
        footer.addStretch(1)
        footer.addWidget(copy)
        line = QFrame()
        line.setObjectName("destDivider")
        line.setFixedHeight(1)
        col.addWidget(line)
        col.addLayout(footer)
        column.hide()
        return column

    def _copy_summary(self) -> None:
        if self._summary_text:
            ensure_app().clipboard().setText(self._summary_text)

    def update(
        self,
        state: MeetingState,
        *,
        capture_status: object,
        transcription_status: object,
        loopback_active: bool | None = None,
        loopback_requested: bool = True,
    ) -> None:
        """Render one immutable state snapshot, capped at three active hints."""
        active = [hint for hint in state.emitted_hints if hint.status == HintStatus.ACTIVE]
        active.sort(key=lambda hint: (-hint.priority, -hint.confidence, hint.id))
        visible = active[:3]
        self._render_topics(state.topics)
        two_column = bool(getattr(state, "live_summary_enabled", False))
        self._render_summary(state.live_summary, enabled=two_column)
        self._render_questions(state.questions)
        self._render_hints(visible, pick_emphasis(visible))
        # Canvas 03: grow to two columns (600px) with a summary column; else 360px.
        self.window.setFixedWidth(600 if two_column else 360)
        if two_column:
            self._summary_time.setText(format_elapsed(self._elapsed_seconds())[:5])
        self._capture_status = capture_status
        interrupted = _enum_value(capture_status) == "error"
        self._listening.setText(
            i18n.t(
                "modules.meeting_buddy.overlay.headline.interrupted"
                if interrupted
                else "modules.meeting_buddy.overlay.headline.listening"
            )
        )
        self._listening.setStyleSheet(f"color: {TOKENS['danger_text']};" if interrupted else "")
        self._update_recording_banner(
            capture_status,
            transcription_status,
            loopback_active=loopback_active,
            loopback_requested=loopback_requested,
        )
        capture = _enum_value(capture_status)
        if capture in {"active", "starting", "reconnecting"}:
            self._source_levels.set_loopback_state(
                loopback_active=loopback_active,
                loopback_requested=loopback_requested,
            )
            self._source_levels.show()
            self._source_levels.refresh()
        else:
            self._source_levels.hide()
        self._update_listening_dot(capture_status, transcription_status)
        self._footer_label.setText(
            "  ·  ".join(
                (
                    self._status_text("capture", capture_status),
                    self._status_text("stt", transcription_status),
                )
            )
        )
        self.window.show()
        if not self._shown_once:
            self._shown_once = True
            self._place_top_right()

    def minimize(self) -> None:
        self.window.hide()
        if self._mini is None:
            self._mini = _MiniPill(self._expand)
        self._mini.set_state(
            format_elapsed(self._elapsed_seconds()), f"{self._topic_done}/{self._topic_total}"
        )
        geometry = self.window.geometry()
        self._mini.move(geometry.right() - self._mini.width(), geometry.top())
        self._mini.show()

    def _expand(self) -> None:
        if self._mini is not None:
            self._mini.hide()
        self.window.show()

    def close(self) -> None:
        self._timer.stop()
        self._levels_timer.stop()
        if self._mini is not None:
            self._mini.close()
            self._mini.deleteLater()
        self.window.close()
        self.window.deleteLater()

    @staticmethod
    def _clear_layout(layout: Any) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            child = item.layout()
            if child is not None:
                # Rows added via addLayout() hold their own widgets; clear those
                # too, otherwise they stay parented and pile up on every update.
                MeetingBuddyOverlay._clear_layout(child)
                child.deleteLater()

    def _render_topics(self, topics: Sequence[Topic]) -> None:
        self._clear_layout(self._topics_body)
        self._topic_total = len(topics)
        self._topic_done = _topics_done(topics)
        if not topics:
            self._topics.hide()
            return
        self._topics_count.setText(f"{self._topic_done}/{self._topic_total}")
        for topic in topics:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(_StatusDot(topic.status), 0, Qt.AlignmentFlag.AlignVCenter)
            label = QLabel(topic.title)
            label.setWordWrap(True)
            weight = "600" if is_at_least_sequential(topic.status) else "400"
            label.setStyleSheet(
                f"color: {topic_line_color(topic)}; font-size: 13px; font-weight: {weight};"
            )
            row.addWidget(label, 1)
            self._topics_body.addLayout(row)
        self._topics.show()

    def _render_questions(self, questions: Sequence[Question]) -> None:
        self._clear_layout(self._questions_body)
        open_questions = [
            question for question in questions if question.status == QuestionStatus.OPEN
        ][:5]
        if not open_questions:
            self._questions.hide()
            return
        self._questions_count.setText(str(len(open_questions)))
        for question in open_questions:
            row = QHBoxLayout()
            row.setSpacing(8)
            mark = QLabel("?")
            mark.setObjectName("overlayQ")
            text = QLabel(question.text)
            text.setObjectName("overlayQText")
            text.setWordWrap(True)
            row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(text, 1)
            self._questions_body.addLayout(row)
        self._questions.show()

    def _render_summary(self, summary: str, *, enabled: bool = False) -> None:
        self._summary_text = (summary or "").strip()
        self._clear_layout(self._summary_bullets)
        if not enabled:
            self._summary_col.hide()
            return
        points = summary_points(self._summary_text)
        if not points:
            waiting = QLabel(i18n.t("modules.meeting_buddy.overlay.summary_waiting"))
            waiting.setWordWrap(True)
            waiting.setStyleSheet(f"color: {TOKENS['muted_soft']}; font-size: 12.5px;")
            self._summary_bullets.addWidget(waiting)
        else:
            for point in points:
                row = QHBoxLayout()
                row.setSpacing(9)
                dot = QLabel()
                dot.setObjectName("summaryDot")
                dot.setFixedSize(6, 6)
                text = QLabel(point)
                text.setObjectName("summaryPoint")
                text.setWordWrap(True)
                row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
                row.addWidget(text, 1)
                self._summary_bullets.addLayout(row)
        self._summary_col.show()

    def _render_hints(self, hints: Sequence[Hint], emphasis_id: str | None) -> None:
        self._clear_layout(self._hints_body)
        self._hint_cards.clear()
        if not hints:
            self._hints_count.setText("")
            self._hints.hide()
            return
        self._hints_count.setText(str(len(hints)))
        for hint in hints:
            emphasized = hint.id == emphasis_id
            card = QFrame()
            card.setObjectName("hintEmph" if emphasized else "hintCard")
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 9, 10, 9)
            card_layout.setSpacing(7)
            if emphasized:
                label = QLabel(i18n.t("modules.meeting_buddy.overlay.hint_important").upper())
                label.setObjectName("hintImportant")
                card_layout.addWidget(label)
            message = QLabel(hint.message)
            message.setWordWrap(True)
            message.setStyleSheet(
                f"color: {TOKENS['text']}; font-size: 12.5px;"
                + (" font-weight: 600;" if emphasized else "")
            )
            card_layout.addWidget(message)
            controls = QHBoxLayout()
            controls.setSpacing(6)
            if _enum_value(hint.type) == HintType.CANDIDATE_ACTION_WITHOUT_OWNER.value:
                confirm = QPushButton(i18n.t("modules.meeting_buddy.overlay.confirm"))
                confirm.setObjectName("primary")
                confirm.clicked.connect(
                    lambda _checked=False, hint_id=hint.id: self._on_confirm(hint_id)
                )
                controls.addWidget(confirm)
            dismiss = QPushButton(i18n.t("modules.meeting_buddy.overlay.dismiss"))
            dismiss.setObjectName("ghost")
            dismiss.clicked.connect(
                lambda _checked=False, hint_id=hint.id: self._on_dismiss(hint_id)
            )
            controls.addWidget(dismiss)
            controls.addStretch(1)
            card_layout.addLayout(controls)
            self._hints_body.addWidget(card)
            self._hint_cards[hint.id] = card
        self._hints.show()

    def _tick(self) -> None:
        timer = format_elapsed(self._elapsed_seconds())
        self._timer_label.setText(timer)
        if self._mini is not None and self._mini.isVisible():
            self._mini.set_state(timer, f"{self._topic_done}/{self._topic_total}")
        if _enum_value(self._capture_status) == "active":
            self._pulse_on = not self._pulse_on
            color = COLOR_RECORDING if self._pulse_on else "#FF9E9B"
            self._listening_dot.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _update_recording_banner(
        self,
        capture_status: object,
        transcription_status: object,
        *,
        loopback_active: bool | None,
        loopback_requested: bool,
    ) -> None:
        layout = self._banner_host.layout()
        assert isinstance(layout, QVBoxLayout)
        self._clear_layout(layout)
        capture = _enum_value(capture_status)
        delayed = _enum_value(transcription_status) == "delayed"
        if capture not in {"active", "starting", "reconnecting", "error"}:
            self._banner_host.hide()
            return

        if capture == "error":
            kind, icon, icon_color = "bannerError", "!", TOKENS["danger"]
            text = i18n.t("modules.meeting_buddy.overlay.recording.error")
        elif capture in {"starting", "reconnecting"}:
            kind, icon, icon_color = "bannerMuted", "●", TOKENS["muted"]
            text = i18n.t("modules.meeting_buddy.overlay.recording.starting")
        elif delayed:
            kind, icon, icon_color = "bannerWarn", "!", TOKENS["amber_icon"]
            text = self._active_recording_text(
                delayed=True, loopback_active=loopback_active, loopback_requested=loopback_requested
            )
        elif loopback_active is True:
            kind, icon, icon_color = "bannerInfo", "♪", TOKENS["accent"]
            text = self._active_recording_text(
                delayed=False, loopback_active=True, loopback_requested=loopback_requested
            )
        elif loopback_requested and loopback_active is False:
            kind, icon, icon_color = "bannerWarn", "!", TOKENS["amber_icon"]
            text = self._active_recording_text(
                delayed=False, loopback_active=False, loopback_requested=True
            )
        else:
            kind, icon, icon_color = "bannerMuted", "●", TOKENS["muted"]
            text = self._active_recording_text(
                delayed=False,
                loopback_active=loopback_active,
                loopback_requested=loopback_requested,
            )

        banner = QFrame()
        banner.setObjectName(kind)
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(banner)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(8)
        glyph = QLabel(icon)
        glyph.setStyleSheet(f"color: {icon_color}; font-weight: 700;")
        message = QLabel(text)
        message.setWordWrap(True)
        message.setStyleSheet(f"color: {TOKENS['text_secondary']}; font-size: 12px;")
        top.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(message, 1)
        box.addLayout(top)
        if capture == "error":
            reconnect = QPushButton(i18n.t("modules.meeting_buddy.overlay.reconnect"))
            reconnect.setObjectName("primary")
            reconnect.clicked.connect(self._on_reconnect)
            actions = QHBoxLayout()
            actions.addWidget(reconnect)
            actions.addStretch(1)
            box.addLayout(actions)
        layout.addWidget(banner)
        self._banner_host.show()

    def _update_listening_dot(self, capture_status: object, transcription_status: object) -> None:
        if _enum_value(capture_status) != "active":
            self._listening_dot.setStyleSheet(
                f"color: {self._listening_color(capture_status, transcription_status)};"
                " font-size: 11px;"
            )

    def _place_top_right(self) -> None:
        self.window.adjustSize()
        screen = self.window.screen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.window.move(geometry.right() - self.window.width() - 24, geometry.top() + 24)

    @staticmethod
    def _status_text(kind: str, status: object) -> str:
        value = _enum_value(status)
        key = f"modules.meeting_buddy.overlay.{kind}.{value}"
        translated = i18n.t(key)
        return f"{i18n.t(f'modules.meeting_buddy.overlay.{kind}')}: {str(value) if translated == key else translated}"

    @staticmethod
    def _active_recording_text(
        *, delayed: bool, loopback_active: bool | None, loopback_requested: bool
    ) -> str:
        if loopback_active is True:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.active_loopback_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.active_loopback"
            )
        if loopback_requested and loopback_active is False:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.mic_only_unavailable_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.mic_only_unavailable"
            )
        if not loopback_requested:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.mic_only_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.mic_only"
            )
        return i18n.t(
            "modules.meeting_buddy.overlay.recording.active_delayed"
            if delayed
            else "modules.meeting_buddy.overlay.recording.active"
        )

    @staticmethod
    def _listening_text(
        capture_status: object,
        transcription_status: object,
        *,
        loopback_active: bool | None = None,
        loopback_requested: bool = True,
    ) -> str:
        capture, stt = _enum_value(capture_status), _enum_value(transcription_status)
        if capture == "error":
            return i18n.t("modules.meeting_buddy.overlay.listening.error")
        if capture in {"starting", "reconnecting"}:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.reconnecting_loopback"
                if capture == "reconnecting" and loopback_requested
                else "modules.meeting_buddy.overlay.listening.starting"
            )
        if capture == "active" and loopback_active is True:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.active_loopback_delayed"
                if stt == "delayed"
                else "modules.meeting_buddy.overlay.listening.active_loopback"
            )
        if capture == "active" and loopback_requested and loopback_active is False:
            return i18n.t("modules.meeting_buddy.overlay.listening.mic_only_unavailable")
        if capture == "active" and not loopback_requested:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.mic_only_delayed"
                if stt == "delayed"
                else "modules.meeting_buddy.overlay.listening.mic_only"
            )
        if capture == "active" and stt == "delayed":
            return i18n.t("modules.meeting_buddy.overlay.listening.delayed")
        if capture == "active":
            return i18n.t("modules.meeting_buddy.overlay.listening.active")
        return i18n.t("modules.meeting_buddy.overlay.listening.idle")

    @staticmethod
    def _listening_color(capture_status: object, transcription_status: object) -> str:
        capture, stt = _enum_value(capture_status), _enum_value(transcription_status)
        if capture == "error":
            return "#E53935"
        if capture in {"starting", "reconnecting"}:
            return "#FFB020"
        if capture == "active" and stt in {"active", "delayed"}:
            return "#43A047"
        return "#9AA0A6"


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
