"""Qt implementation of the transcript destinations dialog."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import destinations
import i18n
import recovery
from ui.app import ensure_app

_open_dialog: QDialog | None = None


def _revalidate_active(dest_list: list[dict[str, Any]], active: str | None) -> str | None:
    return (
        active if active is not None and any(item["name"] == active for item in dest_list) else None
    )


def _dialog_parent(parent: Any) -> QWidget | None:
    return parent if isinstance(parent, QWidget) else None


class DestinationEditor(QDialog):
    """Small modal editor for one custom destination."""

    def __init__(
        self, parent: QWidget | None, title: str, item: dict[str, Any] | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        item = item or {}
        self._result: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(str(item.get("name", "")))
        self.path = QLineEdit(str(item.get("path", "")))
        path_row = QHBoxLayout()
        path_row.addWidget(self.path)
        browse = QPushButton(i18n.t("destinations.browse"))
        browse.clicked.connect(self._browse_folder)
        path_row.addWidget(browse)
        self.auto_paste = QCheckBox(i18n.t("destinations.auto_paste"))
        self.auto_paste.setChecked(bool(item.get("auto_paste", False)))
        self.mode = QComboBox()
        self.mode.addItem(i18n.t("destinations.file_mode.new"), destinations.FILE_MODE_NEW)
        self.mode.addItem(i18n.t("destinations.file_mode.append"), destinations.FILE_MODE_APPEND)
        self.mode.setCurrentIndex(
            1 if item.get("file_mode") == destinations.FILE_MODE_APPEND else 0
        )
        self.append_file = QLineEdit(str(item.get("append_file", "")))
        self._append_widget = QWidget()
        append_row = QHBoxLayout(self._append_widget)
        append_row.setContentsMargins(0, 0, 0, 0)
        append_row.addWidget(self.append_file)
        browse_file = QPushButton(i18n.t("destinations.browse_file"))
        browse_file.clicked.connect(self._browse_file)
        append_row.addWidget(browse_file)
        form.addRow(i18n.t("destinations.name"), self.name)
        form.addRow(i18n.t("destinations.path"), path_row)
        form.addRow("", self.auto_paste)
        form.addRow(i18n.t("destinations.file_mode"), self.mode)
        self._append_label = QLabel(i18n.t("destinations.append_file"))
        form.addRow(self._append_label, append_row)
        layout.addLayout(form)
        self.mode.currentIndexChanged.connect(self._sync_append_file)
        self._sync_append_file()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = buttons.addButton(
            i18n.t("destinations.save"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        save.setObjectName("primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept)
        layout.addWidget(buttons)

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result

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

    def _sync_append_file(self) -> None:
        visible = self.mode.currentData() == destinations.FILE_MODE_APPEND
        self._append_label.setVisible(visible)
        self._append_widget.setVisible(visible)

    def _accept(self) -> None:
        name, path = self.name.text().strip(), self.path.text().strip()
        append_file = self.append_file.text().strip()
        mode = str(self.mode.currentData())
        message = None
        if not name:
            message = i18n.t("destinations.error.name_required")
        elif not path:
            message = i18n.t("destinations.error.path_required")
        elif mode == destinations.FILE_MODE_APPEND and not append_file:
            message = i18n.t("destinations.error.append_file_required")
        if message is not None:
            QMessageBox.warning(self, i18n.t("destinations.title"), message)
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
        self.setMinimumSize(680, 420)
        self._current = current
        self._on_apply = on_apply
        self._destinations = copy.deepcopy(
            destinations.sanitize_destinations(current.get("destinations"))
        )
        self._active = _revalidate_active(self._destinations, current.get("active_destination"))
        layout = QVBoxLayout(self)
        intro = QLabel(i18n.t("destinations.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                i18n.t("destinations.column.name"),
                i18n.t("destinations.column.path"),
                i18n.t("destinations.column.auto_paste"),
                i18n.t("destinations.column.file_mode"),
                i18n.t("destinations.column.active"),
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._sync_selection_buttons)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.add_button = QPushButton(i18n.t("destinations.add"))
        self.edit_button = QPushButton(i18n.t("destinations.edit"))
        self.delete_button = QPushButton(i18n.t("destinations.delete"))
        self.active_button = QPushButton(i18n.t("destinations.active.yes"))
        for button in (self.add_button, self.edit_button, self.delete_button, self.active_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.active_button.clicked.connect(self._set_active)
        folders = QHBoxLayout()
        open_transcripts = QPushButton(i18n.t("destinations.open_transcripts"))
        self.open_active = QPushButton(i18n.t("destinations.open_active"))
        open_transcripts.clicked.connect(
            lambda: destinations.open_in_explorer(recovery.transcripts_dir())
        )
        self.open_active.clicked.connect(self._open_active)
        folders.addWidget(open_transcripts)
        folders.addWidget(self.open_active)
        folders.addStretch()
        layout.addLayout(folders)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = buttons.addButton(
            i18n.t("destinations.save"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        save.setObjectName("primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.table.setRowCount(1 + len(self._destinations))
        default_values = (
            i18n.t("destinations.default.name"),
            i18n.t("destinations.default.path"),
            "—",
            "—",
            i18n.t("destinations.active.yes") if self._active is None else "",
        )
        for column, value in enumerate(default_values):
            self.table.setItem(0, column, QTableWidgetItem(value))
        for row, item in enumerate(self._destinations, 1):
            values = (
                item["name"],
                item["path"],
                i18n.t("destinations.auto_paste.yes")
                if item.get("auto_paste")
                else i18n.t("destinations.auto_paste.no"),
                i18n.t("destinations.file_mode.append.short")
                if item.get("file_mode") == destinations.FILE_MODE_APPEND
                else i18n.t("destinations.file_mode.new.short"),
                i18n.t("destinations.active.yes") if item["name"] == self._active else "",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self._sync_selection_buttons()

    def _selected_index(self) -> int | None:
        row = self.table.currentRow()
        return row - 1 if row > 0 else None

    def _sync_selection_buttons(self) -> None:
        custom = self._selected_index() is not None
        self.edit_button.setEnabled(custom)
        self.delete_button.setEnabled(custom)
        self.active_button.setEnabled(self.table.currentRow() >= 0)
        self.open_active.setEnabled(self._active is not None)

    def _validate_name(self, name: str, skip_index: int | None = None) -> bool:
        if destinations.is_reserved_name(name):
            QMessageBox.warning(
                self, i18n.t("destinations.title"), i18n.t("destinations.error.reserved_name")
            )
            return False
        collision = destinations.find_normalized_collision(
            name, self._destinations, exclude_index=skip_index
        )
        if collision is not None:
            QMessageBox.warning(
                self,
                i18n.t("destinations.title"),
                i18n.t("destinations.error.name_collision", existing=collision),
            )
            return False
        return True

    def _add(self) -> None:
        editor = DestinationEditor(self, i18n.t("destinations.add"))
        if (
            editor.exec()
            and editor.result is not None
            and self._validate_name(editor.result["name"])
        ):
            self._destinations.append(editor.result)
            self._refresh()

    def _edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        editor = DestinationEditor(self, i18n.t("destinations.edit"), self._destinations[index])
        if (
            editor.exec()
            and editor.result is not None
            and self._validate_name(editor.result["name"], index)
        ):
            previous = self._destinations[index]["name"]
            self._destinations[index] = editor.result
            if self._active == previous:
                self._active = editor.result["name"]
            self._refresh()

    def _delete(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        removed = self._destinations.pop(index)
        if self._active == removed["name"]:
            self._active = None
        self._refresh()

    def _set_active(self) -> None:
        index = self._selected_index()
        self._active = None if index is None else self._destinations[index]["name"]
        self._refresh()

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
