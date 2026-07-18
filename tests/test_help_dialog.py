"""Tests voor help_dialog — padresolutie en tekst laden."""

from __future__ import annotations

import i18n
from help_dialog import help_file_path, load_help_text, user_docs_dir


def test_user_docs_dir_exists() -> None:
    assert user_docs_dir().is_dir()


def test_help_file_path_for_ui_language() -> None:
    i18n.set_ui_language("nl")
    path = help_file_path()
    assert path.name == "help.nl.md"
    assert path.is_file()


def test_load_help_text_nl_contains_destinations() -> None:
    i18n.set_ui_language("nl")
    text = load_help_text()
    assert "bestemming" in text.lower()
    assert "standaard" in text.lower()


def test_load_help_text_fallback_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "help_dialog.help_file_path",
        lambda language=None: user_docs_dir() / "help.missing.md",
    )
    text = load_help_text()
    assert text == i18n.t("help.fallback")
