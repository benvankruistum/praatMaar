"""
Instellingen-persistentie voor praatMaar.

Door de gebruiker gewijzigde instellingen worden als `config.json` bewaard in
`%APPDATA%\\praatMaar\\`. De INSTELLINGEN-constanten in `dictation.py`
blijven de defaults; deze config overschrijft ze bij het opstarten.

Bewust puur stdlib (`json`): geen extra dependency voor de configlaag. De
OS-conforme datamap komt van de platform-seam (`host.app_dir()`); deze module
weet dus niet meer van `%APPDATA%` af.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import host


def config_dir() -> Path:
    """De map voor gebruikersinstellingen (OS-conform, via de platform-seam)."""

    return host.app_dir()


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Leest de config; geeft een leeg dict terug als die er niet is of stuk is."""

    path = config_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_config(settings: dict[str, Any]) -> None:
    """Schrijft de config atomisch weg (tmp-bestand + replace)."""

    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = config_path()
    tmp = target.with_name(target.name + ".tmp")

    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2, ensure_ascii=False)

    tmp.replace(target)
