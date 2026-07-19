"""Tests voor help_dialog — padresolutie, markdown→plain en tekst laden."""

from __future__ import annotations

import i18n
from help_dialog import help_file_path, load_help_text, markdown_to_plain, user_docs_dir


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
    assert "##" not in text
    assert "**" not in text
    assert "`" not in text


def test_markdown_to_plain_basics() -> None:
    source = """# Titel

## Sectie

Een **vet** woord en `code`.

- item één
- item twee

| A | B |
|---|---|
| 1 | 2 |
"""
    plain = markdown_to_plain(source)
    assert "Titel" in plain
    assert "Sectie" in plain
    assert "vet" in plain
    assert "code" in plain
    assert "• item één" in plain
    assert "A — B" in plain
    assert "1 — 2" in plain
    assert "#" not in plain
    assert "**" not in plain


def test_load_help_text_fallback_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "help_dialog.help_file_path",
        lambda language=None: user_docs_dir() / "help.missing.md",
    )
    text = load_help_text()
    assert text == i18n.t("help.fallback")
