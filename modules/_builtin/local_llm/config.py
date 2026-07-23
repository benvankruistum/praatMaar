"""Config helpers for the local-llm module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.settings_store import load_config, save_config

MODULE_ID = "local-llm"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"


def load_local_llm_config(app_dir: Path) -> dict[str, Any]:
    data = load_config(app_dir, MODULE_ID)
    return {
        "ollama_base_url": str(data.get("ollama_base_url") or DEFAULT_BASE_URL),
        "ollama_model": str(data.get("ollama_model") or DEFAULT_MODEL),
    }


def save_local_llm_config(app_dir: Path, **updates: Any) -> None:
    current = load_config(app_dir, MODULE_ID)
    current.update(updates)
    save_config(app_dir, MODULE_ID, current)
