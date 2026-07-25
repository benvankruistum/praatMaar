"""Qt destinations dialog — canvas frame #3a fidelity."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import destinations
import i18n
import recovery
from ui.app import ensure_app
from ui.theme import TOKENS

_open_dialog: QDialog | None = None

# Kolombreedtes uit canvas #3a (grid 3px 1fr 246 76 96 82). Naam = 1fr (stretch).
_COL_STRIP = 3
_COL_MAP = 246
_COL_PASTE = 76
_COL_STORAGE = 96
_COL_ACTIVE = 82
_ROW_HEIGHT = 44


def _revalidate_active(dest_list: list[dict[str, Any]], active: str | None) -> str | None:
    return (
        active if active is not None and any(item["name"] == active for item in dest_list) else None
    )


def _dialog_parent(parent: Any) -> QWidget | None:
    return parent if isinstance(parent, QWidget) else None


class _Glyph(QWidget):
    """Small painted icon: a folder or a warning triangle (canvas-drawn)."""

    def __init__(
        self,
        shape: str,
        color: str,
        *,
        width: int = 16,
        height: int = 13,
        dashed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._shape = shape
        self._color = QColor(color)
        self._dashed = dashed
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self._shape == "triangle":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color)
            painter.drawPolygon(QPolygonF([QPointF(w / 2, 0), QPointF(w, h), QPointF(0, h)]))
            return
        pen = QPen(self._color)
        pen.setWidthF(1.5)
        if self._dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        tab_w = w * 0.5
        painter.drawRoundedRect(QRectF(0.75, 0.75, tab_w, 4.0), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(0.75, 3.0, w - 1.5, h - 3.75), 1.5, 1.5)


class _ClickableRow(QFrame):
    """Row frame that reports clicks so the list can drive selection."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # QFrame subclasses only honour stylesheet backgrounds with this flag.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, _event: Any) -> None:  # noqa: N802
        self.clicked.emit()


class _FieldError(QWidget):
    """Inline validation message: red triangle + one line, hidden by default."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        icon = _Glyph("triangle", TOKENS["danger"], width=13, height=12)
        self._label = QLabel()
        self._label.setObjectName("fieldError")
        self._label.setWordWrap(True)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._label, 1)
        self.hide()

    def set_message(self, text: str) -> None:
        self._label.setText(text)


class DestinationEditor(QDialog):
    """Modal editor for one custom destination with inline validation."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        primary_label: str,
        item: dict[str, Any] | None = None,
        *,
        siblings: list[dict[str, Any]] | None = None,
        skip_index: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )
        item = item or {}
        self._siblings = siblings or []
        self._skip_index = skip_index
        self._result: dict[str, Any] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        form = QVBoxLayout(body)
        form.setContentsMargins(18, 16, 18, 18)
        form.setSpacing(16)

        # --- Naam ---
        self.name = QLineEdit(str(item.get("name", "")))
        self.name_error = self._error_label()
        form.addLayout(
            self._field_group(
                i18n.t("destinations.name"),
                self.name,
                error=self.name_error,
                hint=i18n.t("destinations.name.hint"),
                required=True,
            )
        )

        # --- Map ---
        self.path = QLineEdit(str(item.get("path", "")))
        self.path.setStyleSheet(f"font-family: {TOKENS['mono']};")
        browse = QPushButton(i18n.t("destinations.browse"))
        browse.setObjectName("secondary")
        browse.clicked.connect(self._browse_folder)
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        self.path_error = self._error_label()
        form.addLayout(
            self._field_group(
                i18n.t("destinations.path"),
                path_row,
                error=self.path_error,
                required=True,
            )
        )

        # --- Automatisch plakken ---
        self.auto_paste = QCheckBox(i18n.t("destinations.auto_paste.title"))
        self.auto_paste.setChecked(bool(item.get("auto_paste", False)))
        paste_hint = QLabel(i18n.t("destinations.auto_paste.hint"))
        paste_hint.setObjectName("hintLabel")
        paste_hint.setWordWrap(True)
        paste_box = QVBoxLayout()
        paste_box.setContentsMargins(0, 0, 0, 0)
        paste_box.setSpacing(2)
        paste_box.addWidget(self.auto_paste)
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(25, 0, 0, 0)
        hint_row.addWidget(paste_hint)
        paste_box.addLayout(hint_row)
        form.addLayout(paste_box)

        # --- Opslag (radio's) ---
        storage = QVBoxLayout()
        storage.setSpacing(9)
        storage_sep = QFrame()
        storage_sep.setObjectName("destDivider")
        storage_sep.setFixedHeight(1)
        form.addWidget(storage_sep)
        storage_title = QLabel(i18n.t("destinations.file_mode"))
        storage_title.setObjectName("fieldTitle")
        storage.addWidget(storage_title)
        self.mode_new = QRadioButton(i18n.t("destinations.file_mode.new"))
        self.mode_append = QRadioButton(i18n.t("destinations.file_mode.append"))
        group = QButtonGroup(self)
        group.addButton(self.mode_new)
        group.addButton(self.mode_append)
        append_selected = item.get("file_mode") == destinations.FILE_MODE_APPEND
        self.mode_append.setChecked(append_selected)
        self.mode_new.setChecked(not append_selected)
        storage.addWidget(self.mode_new)
        storage.addWidget(self.mode_append)

        self.append_group = QFrame()
        self.append_group.setObjectName("appendGroup")
        append_layout = QVBoxLayout(self.append_group)
        append_layout.setContentsMargins(12, 4, 0, 0)
        append_layout.setSpacing(5)
        self.append_file = QLineEdit(str(item.get("append_file", "")))
        self.append_file.setStyleSheet(f"font-family: {TOKENS['mono']};")
        choose_file = QPushButton(i18n.t("destinations.browse_file"))
        choose_file.setObjectName("secondary")
        choose_file.clicked.connect(self._browse_file)
        append_field_row = QHBoxLayout()
        append_field_row.setContentsMargins(0, 0, 0, 0)
        append_field_row.setSpacing(8)
        append_field_row.addWidget(self.append_file, 1)
        append_field_row.addWidget(choose_file)
        self.append_error = self._error_label()
        append_title = QLabel(i18n.t("destinations.append_file"))
        append_title.setObjectName("fieldTitle")
        append_layout.addWidget(append_title)
        append_layout.addLayout(append_field_row)
        append_layout.addWidget(self.append_error)
        append_hint = QLabel(i18n.t("destinations.append_file.hint"))
        append_hint.setObjectName("hintLabel")
        append_hint.setWordWrap(True)
        append_layout.addWidget(append_hint)
        storage_wrap = QVBoxLayout()
        storage_wrap.setContentsMargins(25, 0, 0, 0)
        storage_wrap.addWidget(self.append_group)
        storage.addLayout(storage_wrap)
        form.addLayout(storage)

        # --- Gereserveerde-namen info (amber) ---
        self.reserved_info = QFrame()
        self.reserved_info.setObjectName("reservedInfo")
        reserved_layout = QHBoxLayout(self.reserved_info)
        reserved_layout.setContentsMargins(11, 9, 11, 9)
        reserved_layout.setSpacing(9)
        reserved_icon = _Glyph("triangle", TOKENS["amber_icon"], width=14, height=13)
        reserved_text = QLabel(i18n.t("destinations.reserved_info"))
        reserved_text.setObjectName("reservedInfoText")
        reserved_text.setWordWrap(True)
        reserved_text.setTextFormat(Qt.TextFormat.RichText)
        reserved_layout.addWidget(reserved_icon, 0, Qt.AlignmentFlag.AlignTop)
        reserved_layout.addWidget(reserved_text, 1)
        form.addWidget(self.reserved_info)
        self.reserved_info.hide()

        outer.addWidget(body, 1)

        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.addStretch(1)
        cancel = QPushButton(i18n.t("destinations.cancel"))
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        primary = QPushButton(primary_label)
        primary.setObjectName("primary")
        primary.clicked.connect(self.attempt_accept)
        footer_layout.addWidget(cancel)
        footer_layout.addWidget(primary)
        outer.addWidget(footer)

        self.mode_new.toggled.connect(self._sync_append_visibility)
        self._sync_append_visibility()

    # -- construction helpers --------------------------------------------
    def _error_label(self) -> _FieldError:
        return _FieldError()

    def _field_group(
        self,
        title: str,
        control: QWidget | QHBoxLayout,
        *,
        error: _FieldError,
        hint: str | None = None,
        required: bool = False,
    ) -> QVBoxLayout:
        group = QVBoxLayout()
        group.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(3)
        label = QLabel(title)
        label.setObjectName("fieldTitle")
        title_row.addWidget(label)
        if required:
            star = QLabel("*")
            star.setObjectName("reqStar")
            title_row.addWidget(star)
        title_row.addStretch(1)
        group.addLayout(title_row)
        if isinstance(control, QHBoxLayout):
            group.addLayout(control)
        else:
            group.addWidget(control)
        group.addWidget(error)
        if hint is not None:
            hint_label = QLabel(hint)
            hint_label.setObjectName("hintLabel")
            hint_label.setWordWrap(True)
            group.addWidget(hint_label)
        return group

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result

    def mode(self) -> str:
        return (
            destinations.FILE_MODE_APPEND
            if self.mode_append.isChecked()
            else destinations.FILE_MODE_NEW
        )

    def _sync_append_visibility(self) -> None:
        self.append_group.setVisible(self.mode_append.isChecked())
        # Resize to content so hiding the append field never leaves a tall footer.
        if self.isVisible():
            self.adjustSize()

    def _browse_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, i18n.t("destinations.browse"), self.path.text()
        )
        if chosen:
            self.path.setText(chosen)

    def _browse_file(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            i18n.t("destinations.browse_file"),
            self.path.text(),
            f"{i18n.t('destinations.file_filter')} (*.txt);;All files (*)",
        )
        if chosen:
            self.append_file.setText(chosen)

    def _set_error(self, widget: QLineEdit, on: bool) -> None:
        widget.setProperty("error", "true" if on else "false")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _show_field_error(self, field: QLineEdit, error: _FieldError, message: str | None) -> None:
        if message:
            error.set_message(message)
            error.show()
            self._set_error(field, True)
        else:
            error.hide()
            self._set_error(field, False)

    def attempt_accept(self) -> None:
        name = self.name.text().strip()
        path = self.path.text().strip()
        append_file = self.append_file.text().strip()
        mode = self.mode()

        name_error: str | None = None
        if not name:
            name_error = i18n.t("destinations.error.name_required")
        elif destinations.is_reserved_name(name):
            name_error = i18n.t("destinations.error.reserved_name")
        else:
            collision = destinations.find_normalized_collision(
                name, self._siblings, exclude_index=self._skip_index
            )
            if collision is not None:
                name_error = i18n.t("destinations.error.name_collision", existing=collision)
        path_error = None if path else i18n.t("destinations.error.path_required")
        append_error = (
            i18n.t("destinations.error.append_file_required")
            if mode == destinations.FILE_MODE_APPEND and not append_file
            else None
        )

        self._show_field_error(self.name, self.name_error, name_error)
        self._show_field_error(self.path, self.path_error, path_error)
        self._show_field_error(self.append_file, self.append_error, append_error)
        self.reserved_info.setVisible(name_error is not None)

        if name_error or path_error or append_error:
            return
        self._result = {
            "name": name,
            "path": path,
            "auto_paste": self.auto_paste.isChecked(),
            "file_mode": mode,
            "append_file": append_file if mode == destinations.FILE_MODE_APPEND else "",
        }
        self.accept()


class DestinationsDialog(QDialog):
    """Manage custom transcript destinations before persisting the changes."""

    def __init__(
        self,
        parent: QWidget | None,
        current: dict[str, Any],
        on_apply: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("destinations.title"))
        self.setMinimumSize(760, 460)
        self.resize(760, 560)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )
        self._current = current
        self._on_apply = on_apply
        self._destinations = copy.deepcopy(
            destinations.sanitize_destinations(current.get("destinations"))
        )
        self._active = _revalidate_active(self._destinations, current.get("active_destination"))
        self._selected: str | int | None = None
        self._row_frames: dict[str | int, _ClickableRow] = {}
        self._row_strips: dict[str | int, QFrame] = {}
        self.active_pill: QLabel | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_intro())
        outer.addWidget(self._build_column_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {TOKENS['surface']}; border: none; }}")
        rows_host = QWidget()
        # Scope to the host so the bare background does not override row rules.
        rows_host.setObjectName("destRowsHost")
        rows_host.setStyleSheet(f"QWidget#destRowsHost {{ background: {TOKENS['surface']}; }}")
        self._rows_layout = QVBoxLayout(rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty_state = self._build_empty_state()
        self._rows_layout.addWidget(self.empty_state)
        scroll.setWidget(rows_host)
        outer.addWidget(scroll, 1)

        outer.addWidget(self._build_action_row())
        outer.addWidget(self._build_footer())

        self._rebuild_rows()
        self._sync_selection()

    # -- shell builders --------------------------------------------------
    def _build_intro(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("destIntro")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        badge = QLabel("?")
        badge.setObjectName("introBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        lines = QVBoxLayout()
        lines.setSpacing(4)
        for key, name in (
            ("destinations.intro.line1", "introLine"),
            ("destinations.intro.line2", "introLine"),
            ("destinations.intro.line3", "introLineMuted"),
        ):
            label = QLabel(i18n.t(key))
            label.setObjectName(name)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            lines.addWidget(label)
        layout.addLayout(lines, 1)
        return frame

    def _build_column_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("destColHeaderRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        layout.addSpacing(_COL_STRIP)
        heads = (
            (i18n.t("destinations.column.name"), 0),
            (i18n.t("destinations.column.path"), _COL_MAP),
            (i18n.t("destinations.column.auto_paste"), _COL_PASTE),
            (i18n.t("destinations.column.file_mode"), _COL_STORAGE),
            (i18n.t("destinations.column.active"), _COL_ACTIVE),
        )
        for text, width in heads:
            label = QLabel(text.upper())
            label.setObjectName("destColHead")
            label.setContentsMargins(12, 9, 12, 9)
            if width:
                label.setFixedWidth(width)
                layout.addWidget(label)
            else:
                layout.addWidget(label, 1)
        return frame

    def _build_empty_state(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(18, 44, 18, 48)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        icon = _Glyph("folder", TOKENS["icon_muted"], width=34, height=26, dashed=True)
        title = QLabel(i18n.t("destinations.empty.title"))
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body = QLabel(i18n.t("destinations.empty.body"))
        body.setObjectName("emptyBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.setMaximumWidth(400)
        cta = QPushButton(i18n.t("destinations.empty.add"))
        cta.setObjectName("primary")
        cta.clicked.connect(self._add)
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(body, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(cta, 0, Qt.AlignmentFlag.AlignHCenter)
        return wrap

    def _build_action_row(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("destActions")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(8)
        self.add_button = QPushButton(i18n.t("destinations.add") + "…")
        self.add_button.setObjectName("primary")
        self.edit_button = QPushButton(i18n.t("destinations.edit") + "…")
        self.edit_button.setObjectName("secondary")
        self.active_button = QPushButton(i18n.t("destinations.set_active"))
        self.active_button.setObjectName("secondary")
        self.delete_button = QPushButton(i18n.t("destinations.delete"))
        self.delete_button.setObjectName("danger")
        for button in (self.add_button, self.edit_button, self.active_button, self.delete_button):
            layout.addWidget(button)
        self.default_hint = QLabel(i18n.t("destinations.default_hint"))
        self.default_hint.setObjectName("hintLabel")
        layout.addWidget(self.default_hint)
        self.default_hint.hide()
        layout.addStretch(1)
        self.open_active = QPushButton(i18n.t("destinations.open_active"))
        self.open_active.setObjectName("link")
        self.open_default = QPushButton(i18n.t("destinations.open_transcripts"))
        self.open_default.setObjectName("link")
        layout.addWidget(self.open_active)
        layout.addWidget(self.open_default)
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.active_button.clicked.connect(self._set_active)
        self.open_active.clicked.connect(self._open_active)
        self.open_default.clicked.connect(
            lambda: destinations.open_in_explorer(recovery.transcripts_dir())
        )
        return frame

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 12, 18, 12)
        note = QLabel(i18n.t("destinations.footer_note"))
        note.setObjectName("footerNote")
        layout.addWidget(note, 1)
        cancel = QPushButton(i18n.t("destinations.cancel"))
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton(i18n.t("destinations.save"))
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        layout.addWidget(cancel)
        layout.addWidget(save)
        return footer

    # -- row building ----------------------------------------------------
    def _cell(self, width: int) -> tuple[QWidget, QHBoxLayout]:
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        if width:
            cell.setFixedWidth(width)
        return cell, layout

    def _make_row(self, key: str | int) -> _ClickableRow:
        row = _ClickableRow()
        row.setObjectName("destRow")
        row.setMinimumHeight(_ROW_HEIGHT)
        row.clicked.connect(lambda k=key: self._on_row_clicked(k))
        return row

    def _rebuild_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.empty_state:
                widget.deleteLater()
        self._row_frames.clear()
        self._row_strips.clear()
        self.active_pill = None

        self._rows_layout.addWidget(self._default_row())
        for index, item in enumerate(self._destinations):
            self._rows_layout.addWidget(self._divider())
            self._rows_layout.addWidget(self._custom_row(index, item))

        has_custom = bool(self._destinations)
        self.empty_state.setVisible(not has_custom)
        if not has_custom:
            self._rows_layout.addWidget(self.empty_state)
        self._apply_row_styles()

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("destDivider")
        line.setFixedHeight(1)
        return line

    def _default_row(self) -> _ClickableRow:
        is_active = self._active is None
        row = self._make_row("default")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._strip("default"))

        name_cell, name_layout = self._cell(0)
        name_layout.addWidget(self._folder_glyph(is_active, muted=True))
        name = QLabel(i18n.t("destinations.default.name"))
        name.setObjectName("destNameMuted")
        name_layout.addWidget(name)
        badge = QLabel(i18n.t("destinations.badge.system").upper())
        badge.setObjectName("systemBadge")
        name_layout.addWidget(badge)
        name_layout.addStretch(1)
        layout.addWidget(name_cell, 1)

        map_cell, map_layout = self._cell(_COL_MAP)
        path = QLabel(i18n.t("destinations.default.path"))
        path.setObjectName("destPathMuted")
        map_layout.addWidget(path)
        map_layout.addStretch(1)
        layout.addWidget(map_cell)

        layout.addWidget(self._text_cell(i18n.t("destinations.auto_paste.no"), _COL_PASTE, True))
        layout.addWidget(
            self._text_cell(i18n.t("destinations.file_mode.new.short"), _COL_STORAGE, True)
        )
        layout.addWidget(self._active_cell(is_active))
        self._row_frames["default"] = row
        return row

    def _custom_row(self, index: int, item: dict[str, Any]) -> _ClickableRow:
        is_active = item["name"] == self._active
        row = self._make_row(index)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._strip(index))

        name_cell, name_layout = self._cell(0)
        name_layout.addWidget(self._folder_glyph(is_active, muted=False))
        name = QLabel(item["name"])
        name.setObjectName("destName")
        name_layout.addWidget(name)
        name_layout.addStretch(1)
        layout.addWidget(name_cell, 1)

        map_cell, map_layout = self._cell(_COL_MAP)
        path = QLabel(item["path"])
        path.setObjectName("destPath")
        map_layout.addWidget(path)
        if destinations.is_shared_location(item["path"]):
            warning = _Glyph("triangle", TOKENS["amber_icon"], width=13, height=12)
            warning.setToolTip(i18n.t("destinations.shared_folder.tooltip"))
            map_layout.addWidget(warning)
        map_layout.addStretch(1)
        layout.addWidget(map_cell)

        paste = i18n.t(
            "destinations.auto_paste.yes"
            if item.get("auto_paste")
            else "destinations.auto_paste.no"
        )
        storage = i18n.t(
            "destinations.file_mode.append.short"
            if item.get("file_mode") == destinations.FILE_MODE_APPEND
            else "destinations.file_mode.new.short"
        )
        layout.addWidget(self._text_cell(paste, _COL_PASTE, False))
        layout.addWidget(self._text_cell(storage, _COL_STORAGE, False))
        layout.addWidget(self._active_cell(is_active))
        self._row_frames[index] = row
        return row

    def _strip(self, key: str | int) -> QFrame:
        strip = QFrame()
        strip.setObjectName("destStrip")
        strip.setFixedWidth(_COL_STRIP)
        self._row_strips[key] = strip
        return strip

    def _folder_glyph(self, is_active: bool, *, muted: bool) -> _Glyph:
        if is_active:
            color = TOKENS["accent"]
        elif muted:
            color = TOKENS["muted_soft"]
        else:
            color = TOKENS["icon_muted"]
        return _Glyph("folder", color, width=15, height=12)

    def _text_cell(self, text: str, width: int, muted: bool) -> QWidget:
        cell, layout = self._cell(width)
        label = QLabel(text)
        label.setObjectName("destCellMuted" if muted else "destCell")
        layout.addWidget(label)
        layout.addStretch(1)
        return cell

    def _active_cell(self, is_active: bool) -> QWidget:
        cell = QWidget()
        cell.setFixedWidth(_COL_ACTIVE)
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        if is_active:
            pill = QLabel("✓ " + i18n.t("destinations.active.badge"))
            pill.setObjectName("activePill")
            layout.addWidget(pill)
            self.active_pill = pill
        layout.addStretch(1)
        return cell

    # -- selection -------------------------------------------------------
    def _on_row_clicked(self, key: str | int) -> None:
        self._selected = key
        self._sync_selection()

    def select_default(self) -> None:
        self._on_row_clicked("default")

    def select_custom(self, index: int) -> None:
        self._on_row_clicked(index)

    def _selected_custom_index(self) -> int | None:
        return self._selected if isinstance(self._selected, int) else None

    def _apply_row_styles(self) -> None:
        for key, frame in self._row_frames.items():
            if key == "default":
                is_active = self._active is None
            else:
                is_active = self._destinations[key]["name"] == self._active
            kind = "active" if is_active else ("system" if key == "default" else "normal")
            frame.setProperty("rowKind", kind)
            frame.setProperty("selected", "true" if key == self._selected else "false")
            frame.style().unpolish(frame)
            frame.style().polish(frame)
            self._row_strips[key].setVisible(is_active)

    def _sync_selection(self) -> None:
        custom = self._selected_custom_index() is not None
        default_selected = self._selected == "default"
        self.edit_button.setEnabled(custom)
        self.delete_button.setEnabled(custom)
        self.active_button.setEnabled(self._selected is not None)
        # Canvas: the default row shows its hint in place of the map-open links.
        self.default_hint.setVisible(default_selected)
        self.open_active.setVisible(not default_selected)
        self.open_default.setVisible(not default_selected)
        self._apply_row_styles()

    # -- actions ---------------------------------------------------------
    def _add(self) -> None:
        editor = DestinationEditor(
            self,
            i18n.t("destinations.editor.add_title"),
            i18n.t("destinations.add"),
            siblings=self._destinations,
        )
        if editor.exec() and editor.result is not None:
            self._destinations.append(editor.result)
            self._selected = len(self._destinations) - 1
            self._rebuild_rows()
            self._sync_selection()

    def _edit(self) -> None:
        index = self._selected_custom_index()
        if index is None:
            return
        editor = DestinationEditor(
            self,
            i18n.t("destinations.editor.edit_title"),
            i18n.t("destinations.save"),
            self._destinations[index],
            siblings=self._destinations,
            skip_index=index,
        )
        if editor.exec() and editor.result is not None:
            previous = self._destinations[index]["name"]
            self._destinations[index] = editor.result
            if self._active == previous:
                self._active = editor.result["name"]
            self._rebuild_rows()
            self._sync_selection()

    def _delete(self) -> None:
        index = self._selected_custom_index()
        if index is None:
            return
        removed = self._destinations.pop(index)
        if self._active == removed["name"]:
            self._active = None
        self._selected = None
        self._rebuild_rows()
        self._sync_selection()

    def _set_active(self) -> None:
        if self._selected == "default":
            self._active = None
        else:
            index = self._selected_custom_index()
            if index is None:
                return
            self._active = self._destinations[index]["name"]
        self._rebuild_rows()
        self._sync_selection()

    def _open_active(self) -> None:
        path = destinations.resolve_save_dir(
            self._active, self._destinations, recovery.transcripts_dir()
        )
        destinations.open_in_explorer(path)

    def _save(self) -> None:
        merged = dict(self._current)
        merged["destinations"] = copy.deepcopy(self._destinations)
        merged["active_destination"] = self._active
        self._on_apply(merged)
        self.accept()


def open_destinations_dialog(
    parent: Any,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    *,
    wait: bool = False,
) -> None:
    """Open the singleton destinations dialog."""
    global _open_dialog
    ensure_app()
    if _open_dialog is not None:
        _open_dialog.raise_()
        _open_dialog.activateWindow()
        if wait:
            _open_dialog.exec()
        return
    dialog = DestinationsDialog(_dialog_parent(parent), current, on_apply)
    _open_dialog = dialog
    dialog.finished.connect(lambda _result: _clear_open_dialog(dialog))
    if wait:
        dialog.exec()
    else:
        dialog.show()


def _clear_open_dialog(dialog: QDialog) -> None:
    global _open_dialog
    if _open_dialog is dialog:
        _open_dialog = None
