"""Shared custom Qt widgets for praatMaar (canvas-aligned)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QWidget

from ui.theme import TOKENS

_TRACK_W = 34
_TRACK_H = 19
_KNOB = 15
_PAD = 2


class ToggleSwitch(QCheckBox):
    """A 34x19 track + sliding knob toggle (canvas switch component).

    Behaves like a ``QCheckBox`` (checkable, toggles on click) but paints the
    canvas on/off switch instead of the default indicator. QSS cannot draw the
    knob reliably, so the widget owns its rendering.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_TRACK_W, _TRACK_H)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(_TRACK_W, _TRACK_H)

    def hitButton(self, pos: Any) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        track = QColor(TOKENS["accent"] if on else TOKENS["border_strong"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, _TRACK_W, _TRACK_H), _TRACK_H / 2, _TRACK_H / 2)
        knob_x = _TRACK_W - _PAD - _KNOB if on else _PAD
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(knob_x, _PAD, _KNOB, _KNOB))
