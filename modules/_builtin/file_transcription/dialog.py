"""PySide6-dialoog voor bestandstranscriptie."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import destinations
import i18n
from modules._builtin.file_transcription.jobs import (
    DialogState,
    FileItem,
    FileItemStatus,
    FileJobHost,
    FileTranscriptionQueue,
)
from ui.app import ensure_app
from ui.theme import TOKENS

_open_dialog: FileTranscriptionDialog | None = None


class FileTranscriptionDialog(QDialog):
    def __init__(
        self,
        *,
        queue: FileTranscriptionQueue,
        host: FileJobHost,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._host = host
        self._pending: list[Path] = []
        self._close_when_idle = False
        self.setWindowTitle(i18n.t("modules.file_transcription.dialog.title"))
        self.setModal(False)
        self.setMinimumWidth(560)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        intro = QLabel(i18n.t("modules.file_transcription.intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        outer.addWidget(intro)

        self._dest_label = QLabel()
        self._dest_path = QLabel()
        self._dest_path.setWordWrap(True)
        self._append_hint = QLabel(i18n.t("modules.file_transcription.append_hint"))
        self._append_hint.setWordWrap(True)
        self._append_hint.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        outer.addWidget(self._dest_label)
        outer.addWidget(self._dest_path)
        outer.addWidget(self._append_hint)

        lang = QLabel(i18n.t("modules.file_transcription.language_hint"))
        lang.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        fmt = QLabel(i18n.t("modules.file_transcription.format_hint"))
        fmt.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        outer.addWidget(lang)
        outer.addWidget(fmt)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        outer.addWidget(self._list, 1)

        self._empty = QLabel(i18n.t("modules.file_transcription.empty"))
        self._empty.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        outer.addWidget(self._empty)

        self._banner = QLabel()
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet(f"color: {TOKENS['text_secondary']}; font-size: 12px;")
        self._banner.hide()
        outer.addWidget(self._banner)

        row = QHBoxLayout()
        self._choose = QPushButton(i18n.t("modules.file_transcription.choose"))
        self._choose.setObjectName("secondary")
        self._choose.clicked.connect(self._choose_files)
        self._remove = QPushButton(i18n.t("modules.file_transcription.remove"))
        self._remove.setObjectName("ghost")
        self._remove.clicked.connect(self._remove_selected)
        self._open_folder = QPushButton(i18n.t("modules.file_transcription.open_folder"))
        self._open_folder.setObjectName("ghost")
        self._open_folder.clicked.connect(self._open_destination_folder)
        row.addWidget(self._choose)
        row.addWidget(self._remove)
        row.addWidget(self._open_folder)
        row.addStretch(1)
        outer.addLayout(row)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._start = QPushButton(i18n.t("modules.file_transcription.start"))
        self._start.setObjectName("primary")
        self._start.setDefault(True)
        self._start.clicked.connect(self._start_job)
        self._stop = QPushButton(i18n.t("modules.file_transcription.stop_queue"))
        self._stop.setObjectName("secondary")
        self._stop.clicked.connect(self._queue.cancel)
        self._copy = QPushButton(i18n.t("modules.file_transcription.to_clipboard"))
        self._copy.setObjectName("ghost")
        self._copy.clicked.connect(self._copy_selected)
        self._close = QPushButton(i18n.t("modules.file_transcription.close"))
        self._close.setObjectName("ghost")
        self._close.clicked.connect(self._on_close_clicked)
        actions.addWidget(self._start)
        actions.addWidget(self._stop)
        actions.addWidget(self._copy)
        actions.addWidget(self._close)
        outer.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        name, folder = self._host.destination_display()
        label = name or i18n.t("modules.file_transcription.destination_default")
        self._dest_label.setText(i18n.t("modules.file_transcription.destination_label", name=label))
        self._dest_path.setText(i18n.t("modules.file_transcription.destination_path", path=folder))
        dest = destinations.find_destination(name, _host_destinations(self._host))
        self._append_hint.setVisible(destinations.resolve_append_file(dest) is not None)

        running = self._queue.is_running()
        rows = (
            self._queue.items
            if running or any(item.status is not FileItemStatus.WAIT for item in self._queue.items)
            else [FileItem(path=path) for path in self._pending]
        )
        self._list.clear()
        for item in rows:
            entry = QListWidgetItem(self._row_text(item))
            entry.setData(Qt.ItemDataRole.UserRole, str(item.path))
            self._list.addItem(entry)
        self._empty.setVisible(self._list.count() == 0)

        state = self._queue.dialog_state
        self._banner.setVisible(state is not DialogState.IDLE or bool(self._banner.text()))
        if state is DialogState.BUSY:
            done = sum(
                1
                for item in self._queue.items
                if item.status
                in {FileItemStatus.DONE, FileItemStatus.ERROR, FileItemStatus.CANCELLED}
            )
            self._banner.setText(
                i18n.t(
                    "modules.file_transcription.busy_status",
                    done=done,
                    total=len(self._queue.items),
                )
            )
            self._banner.show()
        elif state is DialogState.PAUSED:
            self._banner.setText(i18n.t("modules.file_transcription.paused_for_dictation"))
            self._banner.show()
        elif state is DialogState.CANCELLING:
            self._banner.setText(i18n.t("modules.file_transcription.cancel_pending"))
            self._banner.show()
        elif not running and self._queue.items:
            done = sum(1 for item in self._queue.items if item.status is FileItemStatus.DONE)
            errors = sum(1 for item in self._queue.items if item.status is FileItemStatus.ERROR)
            cancelled = sum(
                1 for item in self._queue.items if item.status is FileItemStatus.CANCELLED
            )
            self._banner.setText(
                i18n.t(
                    "modules.file_transcription.summary",
                    done=done,
                    error=errors,
                    cancelled=cancelled,
                )
            )
            self._banner.show()

        idle = state is DialogState.IDLE and not running
        self._choose.setEnabled(idle)
        self._remove.setEnabled(idle)
        self._start.setEnabled(idle and (bool(self._pending) or bool(self._queue.items)))
        self._stop.setEnabled(not idle)
        self._copy.setEnabled(idle)
        if getattr(self, "_close_when_idle", False) and idle:
            self._close_when_idle = False
            self.close()

    def _row_text(self, item: FileItem) -> str:
        status = {
            FileItemStatus.WAIT: i18n.t("modules.file_transcription.item.wait"),
            FileItemStatus.RUNNING: i18n.t("modules.file_transcription.item.running"),
            FileItemStatus.CANCELLED: i18n.t("modules.file_transcription.item.cancelled"),
        }.get(item.status)
        if item.status is FileItemStatus.DONE and item.saved_path is not None:
            status = i18n.t("modules.file_transcription.item.done", name=item.saved_path.name)
        elif item.status is FileItemStatus.ERROR:
            reason = i18n.t(item.error_key) if item.error_key else ""
            status = i18n.t("modules.file_transcription.item.error", reason=reason)
        return f"{item.display_name}    {status or ''}"

    def _choose_files(self) -> None:
        selected, _filter = QFileDialog.getOpenFileNames(
            self,
            i18n.t("modules.file_transcription.choose"),
            "",
            f"{i18n.t('modules.file_transcription.file_filter')} (*.wav)",
        )
        for raw in selected:
            path = Path(raw)
            if path.suffix.lower() != ".wav":
                self._banner.setText(i18n.t("modules.file_transcription.invalid_format"))
                self._banner.show()
                continue
            if path not in self._pending:
                self._pending.append(path)
        self.refresh()

    def _remove_selected(self) -> None:
        chosen = {item.data(Qt.ItemDataRole.UserRole) for item in self._list.selectedItems()}
        self._pending = [path for path in self._pending if str(path) not in chosen]
        self.refresh()

    def _open_destination_folder(self) -> None:
        _name, folder = self._host.destination_display()
        destinations.open_in_explorer(Path(folder))

    def _start_job(self) -> None:
        refused = self._queue.start(list(self._pending))
        if refused is not None:
            self._banner.setText(i18n.t(refused))
            self._banner.show()
            return
        self._pending = []
        self.refresh()

    def _copy_selected(self) -> None:
        selected = {item.data(Qt.ItemDataRole.UserRole) for item in self._list.selectedItems()}
        for item in self._queue.items:
            if (
                str(item.path) in selected
                and item.status is FileItemStatus.DONE
                and item.transcript
            ):
                try:
                    from app.clipboard import copy_to_clipboard_via_qt

                    copy_to_clipboard_via_qt(item.transcript, ui_dispatch=lambda fn: fn())
                    self._banner.setText(i18n.t("modules.file_transcription.clipboard_ok"))
                    self._banner.show()
                except Exception:
                    self._banner.setText(i18n.t("modules.file_transcription.clipboard_fail"))
                    self._banner.show()
                return
        self._banner.setText(i18n.t("modules.file_transcription.select_first"))
        self._banner.show()

    def _on_close_clicked(self) -> None:
        self.close()

    def closeEvent(self, event: object) -> None:
        if self._queue.is_running():
            answer = QMessageBox.question(
                self,
                i18n.t("modules.file_transcription.dialog.title"),
                i18n.t("modules.file_transcription.close_confirm"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()  # type: ignore[attr-defined]
                return
            self._queue.cancel()
            self._close_when_idle = True
            event.ignore()  # type: ignore[attr-defined]
            self.refresh()
            return
        global _open_dialog
        if _open_dialog is self:
            _open_dialog = None
        super().closeEvent(event)  # type: ignore[misc]


def _host_destinations(host: FileJobHost) -> list[dict]:
    return list(host.destinations())


def show_file_transcription_dialog(
    *,
    queue: FileTranscriptionQueue,
    host: FileJobHost,
    existing: QDialog | None,
    parent: QWidget | None = None,
) -> FileTranscriptionDialog:
    ensure_app()
    global _open_dialog
    if isinstance(existing, FileTranscriptionDialog):
        existing.refresh()
        existing.show()
        existing.raise_()
        existing.activateWindow()
        _open_dialog = existing
        return existing
    dialog = FileTranscriptionDialog(queue=queue, host=host, parent=parent)
    _open_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog
