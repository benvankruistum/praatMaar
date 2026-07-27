"""Config helpers for the local-llm module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from modules.settings_store import load_config, save_config

MODULE_ID = "local-llm"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"
ENDPOINT_MODE_BUNDLED = "bundled"
ENDPOINT_MODE_CUSTOM = "custom"
_VALID_MODES = frozenset({ENDPOINT_MODE_BUNDLED, ENDPOINT_MODE_CUSTOM})


class LocalLlmConfigError(ValueError):
    """Ongeldige Local LLM-instelling."""


def normalize_endpoint_mode(value: Any) -> str:
    mode = str(value or ENDPOINT_MODE_BUNDLED).strip().lower()
    if mode not in _VALID_MODES:
        return ENDPOINT_MODE_BUNDLED
    return mode


def validate_base_url(url: str) -> str:
    cleaned = (url or "").strip().rstrip("/")
    if not cleaned:
        raise LocalLlmConfigError("empty_url")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LocalLlmConfigError("invalid_url")
    return cleaned


def validate_model_name(model: str) -> str:
    cleaned = (model or "").strip()
    if not cleaned:
        raise LocalLlmConfigError("empty_model")
    return cleaned


def load_local_llm_config(app_dir: Path) -> dict[str, Any]:
    """Laadt config; ``ollama_*`` zijn de *effectieve* waarden voor de client."""

    data = load_config(app_dir, MODULE_ID)
    mode = normalize_endpoint_mode(data.get("endpoint_mode"))
    stored_url = str(data.get("ollama_base_url") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    stored_model = str(data.get("ollama_model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if mode == ENDPOINT_MODE_BUNDLED:
        effective_url = DEFAULT_BASE_URL
        effective_model = DEFAULT_MODEL
    else:
        try:
            effective_url = validate_base_url(stored_url)
        except LocalLlmConfigError:
            effective_url = DEFAULT_BASE_URL
            mode = ENDPOINT_MODE_BUNDLED
            effective_model = DEFAULT_MODEL
        else:
            try:
                effective_model = validate_model_name(stored_model)
            except LocalLlmConfigError:
                effective_url = DEFAULT_BASE_URL
                effective_model = DEFAULT_MODEL
                mode = ENDPOINT_MODE_BUNDLED

    return {
        "endpoint_mode": mode,
        "ollama_base_url": effective_url,
        "ollama_model": effective_model,
        # Laatst opgeslagen custom-waarden (voor de eigenschappen-UI).
        "custom_base_url": stored_url,
        "custom_model": stored_model,
    }


def save_local_llm_config(app_dir: Path, **updates: Any) -> dict[str, Any]:
    """Slaat updates op en geeft de effectieve config terug."""

    current = load_config(app_dir, MODULE_ID)
    mode = normalize_endpoint_mode(updates.get("endpoint_mode", current.get("endpoint_mode")))

    if mode == ENDPOINT_MODE_CUSTOM:
        url = validate_base_url(
            str(updates["ollama_base_url"])
            if "ollama_base_url" in updates
            else str(current.get("ollama_base_url") or "")
        )
        model = validate_model_name(
            str(updates["ollama_model"])
            if "ollama_model" in updates
            else str(current.get("ollama_model") or "")
        )
        current["endpoint_mode"] = ENDPOINT_MODE_CUSTOM
        current["ollama_base_url"] = url
        current["ollama_model"] = model
    else:
        current["endpoint_mode"] = ENDPOINT_MODE_BUNDLED
        # Bewaar eventuele custom URL/model voor later; forceer geen defaults in file.
        if "ollama_base_url" in updates and updates["ollama_base_url"]:
            try:
                current["ollama_base_url"] = validate_base_url(str(updates["ollama_base_url"]))
            except LocalLlmConfigError:
                pass
        if "ollama_model" in updates and updates["ollama_model"]:
            try:
                current["ollama_model"] = validate_model_name(str(updates["ollama_model"]))
            except LocalLlmConfigError:
                pass

    save_config(app_dir, MODULE_ID, current)
    return load_local_llm_config(app_dir)
