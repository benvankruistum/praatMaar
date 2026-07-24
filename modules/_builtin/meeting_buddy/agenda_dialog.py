"""Qt Meeting Buddy agenda dialog: library, recents, and start/edit flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app

from .agenda_store import (
    default_new_path,
    display_title,
    list_agendas,
    list_recent,
    load_agenda,
    save_agenda,
    touch_recent,
)
from .prep import parse_agenda


@dataclass(frozen=True)
class AgendaDialogResult:
    agenda_text: str
    path: Path | None
    start: bool


def can_start_meeting(body: str) -> bool:
    """Return whether the agenda body has at least one topic."""
    return bool(parse_agenda(body))


def library_sections(
    *, recent: list[Path], all_agendas: list[Path]
) -> list[tuple[str, list[Path]]]:
    """Group library paths into Recent (optional) then All sections."""
    return ([("recent", recent)] if recent else []) + [("all", all_agendas)]


class _AgendaDialog(QDialog):
    def __init__(
        self,
        *,
        agenda_text: str,
        path: Path | None,
        app_dir: Path,
        mode: Literal["start", "edit"],
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._app_dir, self._current_path, self._mode = app_dir, path, mode
        self._result: AgendaDialogResult | None = None
        self.setWindowTitle(i18n.t("modules.meeting_buddy.dialog.title"))
        self.setMinimumSize(680, 420)
        outer = QVBoxLayout(self)
        content = QHBoxLayout()
        self._library = QListWidget()
        self._library.setMinimumWidth(200)
        self._library.itemActivated.connect(self._load_selected)
        self._library.itemClicked.connect(self._load_selected)
        content.addWidget(self._library, 1)
        editor = QVBoxLayout()
        editor.addWidget(QLabel(i18n.t("modules.meeting_buddy.dialog.agenda_prompt")))
        self._agenda = QPlainTextEdit()
        self._agenda.setPlainText(agenda_text)
        self._agenda.textChanged.connect(self._refresh_topic_count)
        editor.addWidget(self._agenda, 1)
        content.addLayout(editor, 2)
        outer.addLayout(content, 1)
        self._topic_count = QLabel()
        outer.addWidget(self._topic_count)
        files = QDialogButtonBox()
        for label, callback in (
            ("modules.meeting_buddy.dialog.open_file", self._open_file),
            ("modules.meeting_buddy.dialog.save", self._save),
            ("modules.meeting_buddy.dialog.save_as", self._save_as),
        ):
            button = files.addButton(i18n.t(label), QDialogButtonBox.ButtonRole.ActionRole)
            button.clicked.connect(callback)
        outer.addWidget(files)
        actions = QDialogButtonBox()
        if mode == "start":
            cancel = actions.addButton(
                i18n.t("modules.meeting_buddy.dialog.cancel"),
                QDialogButtonBox.ButtonRole.RejectRole,
            )
            start = actions.addButton(
                i18n.t("modules.meeting_buddy.dialog.start"), QDialogButtonBox.ButtonRole.AcceptRole
            )
            cancel.clicked.connect(self.reject)
            start.clicked.connect(self._start)
        else:
            close = actions.addButton(
                i18n.t("modules.meeting_buddy.dialog.close"), QDialogButtonBox.ButtonRole.AcceptRole
            )
            close.clicked.connect(self._close_edit)
        outer.addWidget(actions)
        self._populate_library()
        self._refresh_topic_count()

    @property
    def result(self) -> AgendaDialogResult | None:
        return self._result

    def _body(self) -> str:
        return self._agenda.toPlainText().strip()

    def _refresh_topic_count(self) -> None:
        self._topic_count.setText(
            i18n.t(
                "modules.meeting_buddy.dialog.topic_count", count=len(parse_agenda(self._body()))
            )
        )

    def _populate_library(self) -> None:
        self._library.clear()
        for section_id, paths in library_sections(
            recent=list_recent(self._app_dir), all_agendas=list_agendas(self._app_dir)
        ):
            heading = QListWidgetItem(i18n.t(f"modules.meeting_buddy.dialog.{section_id}"))
            heading.setFlags(heading.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # type: ignore[name-defined]
            self._library.addItem(heading)
            for item_path in paths:
                item = QListWidgetItem(f"  {display_title(item_path)}")
                item.setData(Qt.ItemDataRole.UserRole, item_path)  # type: ignore[name-defined]
                self._library.addItem(item)

    def _load_selected(self, item: QListWidgetItem) -> None:
        item_path = item.data(Qt.ItemDataRole.UserRole)  # type: ignore[name-defined]
        if not isinstance(item_path, Path):
            return
        _title, body = load_agenda(item_path)
        self._agenda.setPlainText(body)
        self._current_path = item_path
        touch_recent(self._app_dir, item_path)

    def _require_topics(self) -> bool:
        if can_start_meeting(self._body()):
            return True
        from ui.dialogs.message import warning

        warning(
            i18n.t("modules.meeting_buddy.dialog.title"),
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
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, Path(chosen))  # type: ignore[name-defined]
            self._load_selected(item)

    def _start(self) -> None:
        if self._require_topics():
            if self._current_path is not None:
                touch_recent(self._app_dir, self._current_path)
            self._result = AgendaDialogResult(self._body(), self._current_path, True)
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
    parent: Any = None,
) -> AgendaDialogResult | None:
    """Show agenda UI; return ``None`` on cancel (start mode only)."""
    ensure_app()
    dialog = _AgendaDialog(
        agenda_text=agenda_text,
        path=path,
        app_dir=app_dir,
        mode=mode,
        parent=parent if isinstance(parent, QWidget) else None,
    )
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.exec()
    return dialog.result
