"""i18n voor ingebouwde modules — keys aanwezig en standalone beschrijvingen."""

from __future__ import annotations

import json
import re
from pathlib import Path

from modules.registry import all_builtin_modules

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
LANGUAGES = ("nl", "en", "de")

# Andere module-namen horen niet in elkaars beschrijving (Meeting Buddy mag zichzelf wel).
_CROSS_MODULE_NAME = re.compile(r"meeting[\s-]?buddy", re.IGNORECASE)


def _load_locale(lang: str) -> dict[str, str]:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def test_builtin_module_i18n_keys_exist_in_all_locales() -> None:
    for lang in LANGUAGES:
        strings = _load_locale(lang)
        for module in all_builtin_modules():
            assert strings.get(module.display_name_key()), f"{lang}: missing {module.display_name_key()}"
            assert strings.get(module.description_key()), f"{lang}: missing {module.description_key()}"


def test_module_descriptions_do_not_name_other_modules() -> None:
    for lang in LANGUAGES:
        strings = _load_locale(lang)
        for module in all_builtin_modules():
            if module.id == "meeting-buddy":
                continue
            description = strings[module.description_key()]
            assert _CROSS_MODULE_NAME.search(description) is None, (
                f"{lang}/{module.id}: description names another module: {description!r}"
            )
