"""Tests voor i18n (UI-vertalingen)."""

from __future__ import annotations

import i18n


def test_normalize_language() -> None:
    assert i18n.normalize_language("EN") == "en"
    assert i18n.normalize_language("de-DE") == "de"
    assert i18n.normalize_language("fr") == "nl"
    assert i18n.normalize_language(None) == "nl"


def test_t_english() -> None:
    i18n.set_ui_language("en")
    assert i18n.t("tray.settings") == "Settings"
    assert i18n.t("ready", hotkey="Ctrl+Space").startswith("Ready.")


def test_t_fallback_to_nl() -> None:
    i18n.set_ui_language("en")
    # Onbekende key blijft de key.
    assert i18n.t("does.not.exist") == "does.not.exist"


def test_speech_codes_supported() -> None:
    for code in ("nl", "en", "de"):
        assert (
            i18n.normalize_language(code, allowed=i18n.SUPPORTED_SPEECH_LANGUAGES)
            == code
        )
