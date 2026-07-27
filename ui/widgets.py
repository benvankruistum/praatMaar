"""Shared custom Qt widgets for praatMaar (canvas-aligned)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QLayout, QLayoutItem, QWidget

from ui.theme import TOKENS


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items to the next row (canvas action rows)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margin: int = 0,
        hspacing: int = 6,
        vspacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _layout(self, rect: QRect, *, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspacing
            if next_x - self._hspacing > area.right() and line_height > 0:
                x = area.x()
                y = y + line_height + self._vspacing
                next_x = x + hint.width() + self._hspacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


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
