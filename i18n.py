"""
UI-vertalingen voor praatMaar.

Spraakherkenning (Whisper) is een apart config-veld (`speech_language`).
Deze module gaat alleen over interface-teksten via JSON onder `locales/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SUPPORTED_UI_LANGUAGES = ("nl", "en", "de")
SUPPORTED_SPEECH_LANGUAGES = ("nl", "en", "de")
DEFAULT_LANGUAGE = "nl"

# Weergavenamen (altijd in de eigen taal van die optie — herkenbaar in elke UI).
LANGUAGE_LABELS: dict[str, str] = {
    "nl": "Nederlands",
    "en": "English",
    "de": "Deutsch",
}

_ui_language: str = DEFAULT_LANGUAGE
_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}


def locales_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "locales"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "locales"


def normalize_language(code: Any, *, allowed: tuple[str, ...] = SUPPORTED_UI_LANGUAGES) -> str:
    """Normaliseert naar een ondersteunde code; anders default."""

    if not isinstance(code, str):
        return DEFAULT_LANGUAGE
    cleaned = code.strip().lower().replace("_", "-")
    if cleaned in allowed:
        return cleaned
    primary = cleaned.split("-", 1)[0]
    if primary in allowed:
        return primary
    return DEFAULT_LANGUAGE


def _load_file(code: str) -> dict[str, str]:
    path = locales_dir() / f"{code}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def set_ui_language(code: str) -> str:
    """Laadt UI-strings; geeft de effectieve taalcode terug."""

    global _ui_language, _strings, _fallback

    _fallback = _load_file(DEFAULT_LANGUAGE)
    _ui_language = normalize_language(code, allowed=SUPPORTED_UI_LANGUAGES)
    if _ui_language == DEFAULT_LANGUAGE:
        _strings = dict(_fallback)
    else:
        _strings = _load_file(_ui_language)
    return _ui_language


def ui_language() -> str:
    return _ui_language


def t(key: str, **kwargs: Any) -> str:
    """Vertaalt een key; ontbrekend → NL-fallback → key zelf."""

    if not _strings and not _fallback:
        set_ui_language(_ui_language)

    template = _strings.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


# Laad NL bij import zodat vroege callers iets hebben.
set_ui_language(DEFAULT_LANGUAGE)
