"""
Eenvoudige per-module instellingen op schijf.

Elke module krijgt een eigen map onder de app-datamap, bijv.
``%APPDATA%\\praatMaar\\meeting-buddy\\config.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def module_dir(app_dir: Path, module_id: str) -> Path:
    """Datamap voor één module (kebab-case ``module_id``)."""

    return app_dir / module_id


def config_path(app_dir: Path, module_id: str) -> Path:
    return module_dir(app_dir, module_id) / "config.json"


def load_config(
    app_dir: Path, module_id: str, *, default: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Leest module-config; ontbrekend of ongeldig bestand → ``default`` of ``{}``."""

    path = config_path(app_dir, module_id)
    fallback = dict(default or {})
    if not path.is_file():
        return fallback
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(raw, dict):
        return fallback
    return raw


def save_config(app_dir: Path, module_id: str, data: dict[str, Any]) -> None:
    """Schrijft module-config atomisch naar ``config.json``."""

    directory = module_dir(app_dir, module_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
