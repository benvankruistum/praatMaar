"""Tests for shared UI theme tokens."""

from __future__ import annotations

import ui_theme


def test_accent_and_pill_tokens() -> None:
    assert ui_theme.COLOR_ACCENT == "#0F6CBD"
    assert ui_theme.COLOR_PILL_BG == "#1C1F23"
    assert "meeting-buddy" in ui_theme.EXPERIMENTAL_MODULE_IDS
    assert "local-llm" in ui_theme.EXPERIMENTAL_MODULE_IDS


def test_locale_keys_for_module_hints_exist() -> None:
    import i18n

    i18n.set_ui_language("nl")
    assert "Ollama" in i18n.t("modules.local_llm.dependency_hint")
    assert "Audio" in i18n.t("modules.meeting_buddy.dependency_hint")
    assert i18n.t("modules.badge.experimental") == "experimenteel"
