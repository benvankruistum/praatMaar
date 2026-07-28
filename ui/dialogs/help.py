"""Qt implementation of praatMaar's documentation dialog."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout, QWidget

import i18n
from ui.app import ensure_app

_open_dialog: QDialog | None = None
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def user_docs_dir() -> Path:
    """Return the bundled or repository ``docs/user`` directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "docs" / "user"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "docs" / "user"


def help_file_path(language: str | None = None) -> Path:
    code = i18n.normalize_language(language or i18n.ui_language())
    return user_docs_dir() / f"help.{code}.md"


def _inline_markdown(text: str) -> str:
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = _CODE_RE.sub(r"\1", text)
    return _LINK_RE.sub(r"\1", text)


def markdown_to_plain(source: str) -> str:
    """Render the supported lightweight Markdown subset as readable plain text."""
    out: list[str] = []
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
        elif stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not (cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)):
                out.append(" — ".join(_inline_markdown(cell) for cell in cells if cell))
        elif stripped.startswith("#"):
            if out and out[-1] != "":
                out.append("")
            out.extend((_inline_markdown(stripped.lstrip("#").strip()), ""))
        elif stripped.startswith("- "):
            out.append(f"• {_inline_markdown(stripped[2:])}")
        elif not (set(stripped) <= {"-", "*", "_"} and len(stripped) >= 3):
            out.append(_inline_markdown(stripped))
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def load_help_text(language: str | None = None) -> str:
    """Read translated help text, falling back to the localised short message."""
    try:
        return markdown_to_plain(help_file_path(language).read_text(encoding="utf-8"))
    except OSError:
        return i18n.t("help.fallback")


def open_help(parent: Any, *, wait: bool = False) -> None:
    """Open the singleton read-only help dialog."""
    global _open_dialog
    ensure_app()
    if _open_dialog is not None:
        _open_dialog.raise_()
        _open_dialog.activateWindow()
        if wait:
            _open_dialog.exec()
        return
    dialog_parent = parent if isinstance(parent, QWidget) else None
    dialog = QDialog(dialog_parent)
    dialog.setWindowTitle(i18n.t("help.title"))
    dialog.setMinimumSize(560, 480)
    layout = QVBoxLayout(dialog)
    text = QPlainTextEdit()
    text.setReadOnly(True)
    text.setPlainText(load_help_text())
    layout.addWidget(text)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
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
    # Ook de C++-widgetboom vrijgeven: de dialoog hangt onder de pill en bleef
    # anders tot app-exit bestaan (accumulatie bij herhaald openen).
    dialog.deleteLater()
