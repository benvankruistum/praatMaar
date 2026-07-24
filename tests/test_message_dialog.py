"""Tests for the module-facing Qt message wrappers."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ui.dialogs import message


def test_info_uses_qmessagebox(monkeypatch) -> None:
    called: list[tuple[object, str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: called.append((parent, title, text)),
    )

    message.info("Title", "Body")

    assert called == [(None, "Title", "Body")]
