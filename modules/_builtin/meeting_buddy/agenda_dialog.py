"""Qt Meeting Buddy agenda dialog: library, recents, and start/edit flows."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app
from ui.theme import TOKENS
from ui.widgets import ToggleSwitch

from .agenda_store import (
    default_new_path,
    display_title,
    list_agendas,
    list_recent,
    load_agenda,
    save_agenda,
    touch_recent,
)
from .devices import list_loopback_output_devices
from .prep import parse_agenda
from .properties_dialog import device_selection_maps

CaptureSetupPlatform = Literal["windows", "macos", "other"]


def capture_setup_platform() -> CaptureSetupPlatform:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "other"


@dataclass(frozen=True)
class AgendaDialogResult:
    agenda_text: str
    path: Path | None
    start: bool
    enable_loopback: bool = False
    loopback_device: int | None = None


def can_start_meeting(body: str) -> bool:
    """Return whether the agenda body has at least one topic."""
    return bool(parse_agenda(body))


def library_sections(
    *, recent: list[Path], all_agendas: list[Path]
) -> list[tuple[str, list[Path]]]:
    """Group library paths into Recent (optional) then All sections."""
    return ([("recent", recent)] if recent else []) + [("all", all_agendas)]


class _LineGutter(QWidget):
    """Line-number margin painted by its owning editor."""

    def __init__(self, editor: _LineNumberedEdit) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        self._editor.paint_gutter(event)


class _LineNumberedEdit(QPlainTextEdit):
    """Plain-text editor with a numbered gutter (canvas "één per regel")."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gutter = _LineGutter(self)
        self.blockCountChanged.connect(lambda _count: self._update_margins())
        self.updateRequest.connect(self._on_update)
        self._update_margins()

    def gutter_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margins(self) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _on_update(self, rect: Any, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margins()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event: Any) -> None:
        painter = QPainter(self._gutter)
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        painter.setPen(QColor(TOKENS["muted_soft"]))
        painter.setFont(self.font())
        line_h = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    int(top),
                    self._gutter.width() - 8,
                    line_h,
                    Qt.AlignmentFlag.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            number += 1


class _LibRow(QFrame):
    """Clickable library entry: title with an optional date subtitle."""

    clicked = Signal(object)

    def __init__(self, path: Path, *, subtitle: str | None = None, active: bool = False) -> None:
        super().__init__()
        self.setObjectName("libRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("active", "true" if active else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path = path
        box = QVBoxLayout(self)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(1)
        title = QLabel(display_title(path))
        title.setObjectName("libTitle")
        box.addWidget(title)
        if subtitle:
            date = QLabel(subtitle)
            date.setObjectName("libDate")
            box.addWidget(date)

    def mousePressEvent(self, _event: Any) -> None:  # noqa: N802
        self.clicked.emit(self._path)


class _AgendaDialog(QDialog):
    def __init__(
        self,
        *,
        agenda_text: str,
        path: Path | None,
        app_dir: Path,
        mode: Literal["start", "edit"],
        enable_loopback: bool = False,
        loopback_device: int | None = None,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._app_dir, self._current_path, self._mode = app_dir, path, mode
        self._result: AgendaDialogResult | None = None
        self.setWindowTitle(i18n.t("modules.meeting_buddy.dialog.agenda_title"))
        self.setMinimumSize(620, 440)
        self.resize(620, 500)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QWidget()
        grid = QHBoxLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # --- topics (left) ---
        left = QWidget()
        col = QVBoxLayout(left)
        col.setContentsMargins(18, 14, 18, 16)
        col.setSpacing(8)
        head = QHBoxLayout()
        topics_label = QLabel(i18n.t("modules.meeting_buddy.dialog.topics_label").upper())
        topics_label.setObjectName("sectionLabel")
        one_per_line = QLabel(i18n.t("modules.meeting_buddy.dialog.one_per_line"))
        one_per_line.setObjectName("hintLabel")
        head.addWidget(topics_label)
        head.addStretch(1)
        head.addWidget(one_per_line)
        col.addLayout(head)
        self._agenda = _LineNumberedEdit()
        self._agenda.setObjectName("agendaEditor")
        self._agenda.setMinimumHeight(230)
        self._agenda.setPlainText(agenda_text)
        self._agenda.textChanged.connect(self._refresh_topic_count)
        col.addWidget(self._agenda, 1)
        self._topic_count = QLabel()
        self._topic_count.setObjectName("hintLabel")
        col.addWidget(self._topic_count)
        if mode == "start":
            col.addWidget(
                self._build_capture_setup(
                    enable_loopback=enable_loopback,
                    loopback_device=loopback_device,
                )
            )
        grid.addWidget(left, 1)

        # --- library (right) ---
        self._library_pane = QFrame()
        self._library_pane.setObjectName("agendaLibrary")
        self._library_pane.setFixedWidth(216)
        self._lib_layout = QVBoxLayout(self._library_pane)
        self._lib_layout.setContentsMargins(14, 14, 14, 16)
        self._lib_layout.setSpacing(8)
        grid.addWidget(self._library_pane)
        outer.addWidget(body, 1)

        # --- footer ---
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(18, 12, 18, 12)
        row.setSpacing(8)
        for key, callback in (
            ("modules.meeting_buddy.dialog.open_file", self._open_file),
            ("modules.meeting_buddy.dialog.save", self._save),
            ("modules.meeting_buddy.dialog.save_as", self._save_as),
        ):
            button = QPushButton(i18n.t(key))
            button.setObjectName("secondary")
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch(1)
        if mode == "start":
            cancel = QPushButton(i18n.t("modules.meeting_buddy.dialog.cancel"))
            cancel.setObjectName("ghost")
            cancel.clicked.connect(self.reject)
            start = QPushButton(i18n.t("modules.meeting_buddy.dialog.start"))
            start.setObjectName("primary")
            start.clicked.connect(self._start)
            row.addWidget(cancel)
            row.addWidget(start)
        else:
            close = QPushButton(i18n.t("modules.meeting_buddy.dialog.close"))
            close.setObjectName("primary")
            close.clicked.connect(self._close_edit)
            row.addWidget(close)
        outer.addWidget(footer)

        self._populate_library()
        self._refresh_topic_count()

    @property
    def result(self) -> AgendaDialogResult | None:
        return self._result

    def _body(self) -> str:
        return self._agenda.toPlainText().strip()

    def _refresh_topic_count(self) -> None:
        count = i18n.t(
            "modules.meeting_buddy.dialog.topic_count", count=len(parse_agenda(self._body()))
        )
        if self._current_path is not None:
            count = f"{count}  ·  " + i18n.t(
                "modules.meeting_buddy.dialog.saved_as", name=self._current_path.name
            )
        self._topic_count.setText(count)

    def _build_capture_setup(
        self,
        *,
        enable_loopback: bool,
        loopback_device: int | None,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("agendaCaptureSetup")
        box = QVBoxLayout(frame)
        box.setContentsMargins(0, 8, 0, 0)
        box.setSpacing(8)

        title = QLabel(i18n.t("modules.meeting_buddy.dialog.capture_title").upper())
        title.setObjectName("sectionLabel")
        box.addWidget(title)

        platform = capture_setup_platform()
        desc = QLabel(
            i18n.t(
                "modules.meeting_buddy.dialog.capture_loopback_desc"
                if platform == "windows"
                else "modules.meeting_buddy.dialog.capture_mic_only_desc"
            )
        )
        desc.setObjectName("hintLabel")
        desc.setWordWrap(True)
        box.addWidget(desc)

        self._loopback_device = loopback_device
        if platform == "windows":
            self._loopback = ToggleSwitch()
            self._loopback.setChecked(enable_loopback)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            toggle_label = QLabel(i18n.t("modules.meeting_buddy.settings.loopback_title"))
            toggle_label.setObjectName("mbTitle")
            row.addWidget(toggle_label, 1)
            row.addWidget(self._loopback, 0, Qt.AlignmentFlag.AlignTop)
            box.addLayout(row)

            devices = list_loopback_output_devices()
            labels, self._device_values, _, current = device_selection_maps(
                devices, loopback_device
            )
            self._device = QComboBox()
            self._device.addItems(labels)
            if current in labels:
                self._device.setCurrentText(current)
            self._device.setEnabled(enable_loopback)
            self._loopback.toggled.connect(self._device.setEnabled)
            device_row = QHBoxLayout()
            device_row.setContentsMargins(0, 0, 0, 0)
            device_row.setSpacing(12)
            device_label = QLabel(i18n.t("modules.meeting_buddy.dialog.capture_loopback_device"))
            device_label.setObjectName("fieldLabel")
            device_label.setFixedWidth(150)
            device_row.addWidget(device_label)
            device_row.addWidget(self._device, 1)
            box.addLayout(device_row)
        else:
            self._loopback = None
            self._device = None
            self._device_values = {}

        return frame

    def _capture_settings(self) -> tuple[bool, int | None]:
        if self._mode != "start" or capture_setup_platform() != "windows":
            return False, None
        assert self._loopback is not None
        assert self._device is not None
        enabled = self._loopback.isChecked()
        if not enabled:
            return False, None
        label = self._device.currentText()
        return True, self._device_values.get(label, self._loopback_device)

    @staticmethod
    def _date_label(path: Path) -> str | None:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%m-%Y")
        except OSError:
            return None

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
                _AgendaDialog._clear_layout(child)
                child.deleteLater()

    def _populate_library(self) -> None:
        self._clear_layout(self._lib_layout)
        heading_keys = {"recent": "recent", "all": "all_agendas"}
        for section_id, paths in library_sections(
            recent=list_recent(self._app_dir), all_agendas=list_agendas(self._app_dir)
        ):
            heading = QLabel(
                i18n.t(f"modules.meeting_buddy.dialog.{heading_keys[section_id]}").upper()
            )
            heading.setObjectName("sectionLabel")
            self._lib_layout.addWidget(heading)
            for item_path in paths:
                row = _LibRow(
                    item_path,
                    subtitle=self._date_label(item_path) if section_id == "recent" else None,
                    active=item_path == self._current_path,
                )
                row.clicked.connect(self._open_path)
                self._lib_layout.addWidget(row)
        self._lib_layout.addStretch(1)
        note = QHBoxLayout()
        note.setSpacing(6)
        check = QLabel("✓")
        check.setStyleSheet(
            f"background: {TOKENS['ok']}; color: white; font-size: 8px; font-weight: 700;"
            " border-radius: 6px; min-width: 13px; max-width: 13px; min-height: 13px;"
            " max-height: 13px;"
        )
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(i18n.t("modules.meeting_buddy.dialog.local_saved"))
        text.setObjectName("libDate")
        text.setWordWrap(True)
        note.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
        note.addWidget(text, 1)
        self._lib_layout.addLayout(note)

    def _open_path(self, item_path: Path) -> None:
        if not isinstance(item_path, Path):
            return
        _title, body = load_agenda(item_path)
        self._agenda.setPlainText(body)
        self._current_path = item_path
        touch_recent(self._app_dir, item_path)
        self._populate_library()
        self._refresh_topic_count()

    def _require_topics(self) -> bool:
        if can_start_meeting(self._body()):
            return True
        from ui.dialogs.message import warning

        warning(
            i18n.t("modules.meeting_buddy.dialog.agenda_title"),
            i18n.t("modules.meeting_buddy.dialog.empty_agenda"),
            parent=self,
        )
        self._agenda.setFocus()
        return False

    def _save_to(self, target: Path) -> bool:
        if not self._require_topics():
            return False
        save_agenda(target, self._body())
        self._current_path = target
        touch_recent(self._app_dir, target)
        self._populate_library()
        self._refresh_topic_count()
        return True

    def _save(self) -> None:
        self._save_to(self._current_path or default_new_path(self._app_dir, self._body()))

    def _save_as(self) -> None:
        initial = self._current_path or default_new_path(self._app_dir, self._body())
        chosen, _filter = QFileDialog.getSaveFileName(
            self,
            i18n.t("modules.meeting_buddy.dialog.save_as"),
            str(initial),
            "Markdown (*.md);;All files (*)",
        )
        if chosen:
            self._save_to(Path(chosen))

    def _open_file(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            i18n.t("modules.meeting_buddy.dialog.open_file"),
            "",
            "Markdown (*.md);;All files (*)",
        )
        if chosen:
            self._open_path(Path(chosen))

    def _start(self) -> None:
        if self._require_topics():
            if self._current_path is not None:
                touch_recent(self._app_dir, self._current_path)
            enable_loopback, loopback_device = self._capture_settings()
            self._result = AgendaDialogResult(
                self._body(),
                self._current_path,
                True,
                enable_loopback=enable_loopback,
                loopback_device=loopback_device,
            )
            self.accept()

    def _close_edit(self) -> None:
        self._result = AgendaDialogResult(self._body(), self._current_path, False)
        self.accept()


def show_agenda_dialog(
    *,
    agenda_text: str,
    path: Path | None,
    app_dir: Path,
    mode: Literal["start", "edit"],
    enable_loopback: bool = False,
    loopback_device: int | None = None,
    parent: Any = None,
) -> AgendaDialogResult | None:
    """Show agenda UI; return ``None`` on cancel (start mode only)."""
    ensure_app()
    dialog = _AgendaDialog(
        agenda_text=agenda_text,
        path=path,
        app_dir=app_dir,
        mode=mode,
        enable_loopback=enable_loopback,
        loopback_device=loopback_device,
        parent=parent if isinstance(parent, QWidget) else None,
    )
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.exec()
    return dialog.result
