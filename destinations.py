import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Stem-reset naar de defaultmap. Alle talen + "default" worden altijd geaccepteerd,
# zodat reset werkt ongeacht spraak-/interfacetaal.
RESET_PHRASES = frozenset({"standaard", "default", "standard"})
RESET_PHRASE = "standaard"  # backwards-compat alias
FILE_MODE_NEW = "new"
FILE_MODE_APPEND = "append"


def normalize_phrase(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def match_command(transcript: str, destinations: list[dict[str, Any]]) -> tuple[str, str | None]:
    needle = normalize_phrase(transcript)
    if not needle:
        return ("none", None)
    if needle in RESET_PHRASES:
        return ("reset", None)
    for item in destinations:
        name = str(item.get("name", ""))
        if normalize_phrase(name) == needle:
            return ("set", name)
    return ("none", None)


def find_destination(
    active_name: str | None, destinations: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not active_name:
        return None
    for item in destinations:
        if item.get("name") == active_name:
            return item
    return None


def resolve_save_dir(
    active_name: str | None, destinations: list[dict[str, Any]], default_dir: Path
) -> Path:
    item = find_destination(active_name, destinations)
    if item is not None:
        return Path(str(item["path"]))
    return default_dir


def resolve_file_mode(destination: dict[str, Any] | None) -> str:
    if destination is None:
        return FILE_MODE_NEW
    mode = str(destination.get("file_mode", FILE_MODE_NEW))
    if mode == FILE_MODE_APPEND:
        return FILE_MODE_APPEND
    return FILE_MODE_NEW


def resolve_append_file(destination: dict[str, Any] | None) -> Path | None:
    if destination is None or resolve_file_mode(destination) != FILE_MODE_APPEND:
        return None
    raw = str(destination.get("append_file", "")).strip()
    if not raw:
        return None
    return Path(raw)


def resolve_auto_paste(
    active_name: str | None,
    destinations: list[dict[str, Any]],
    global_auto_paste: bool,
) -> bool:
    """
    Effectieve plak/klembord-modus.

    Met actieve bestemming wint die flag; zonder actieve geldt de globale setting.
    Ontbrekende `auto_paste` op een bestemming telt als False.
    """

    if active_name:
        for item in destinations:
            if item.get("name") == active_name:
                return bool(item.get("auto_paste", False))
    return bool(global_auto_paste)


def open_in_explorer(path: Path) -> None:
    """Opent een map in de bestandsverkenner (Windows / macOS)."""

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    # resolve(): Store-Python virtualiseert %APPDATA%; Verkenner heeft het
    # canonieke pad nodig (anders "Location is not available").
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        raise RuntimeError(f"Map openen niet ondersteund op {sys.platform!r}")


def is_reserved_name(name: str) -> bool:
    return normalize_phrase(name) in RESET_PHRASES


def find_normalized_collision(
    name: str,
    destinations: list[dict[str, Any]],
    *,
    exclude_index: int | None = None,
) -> str | None:
    needle = normalize_phrase(name)
    if not needle:
        return None
    for index, item in enumerate(destinations):
        if exclude_index is not None and index == exclude_index:
            continue
        existing = str(item.get("name", ""))
        if normalize_phrase(existing) == needle:
            return existing
    return None


def sanitize_destinations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen_normalized: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        path = str(item.get("path", "")).strip()
        if not name or not path:
            continue
        if is_reserved_name(name):
            continue
        normalized = normalize_phrase(name)
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        file_mode = str(item.get("file_mode", FILE_MODE_NEW))
        if file_mode not in (FILE_MODE_NEW, FILE_MODE_APPEND):
            file_mode = FILE_MODE_NEW
        append_file = str(item.get("append_file", "")).strip()
        if file_mode == FILE_MODE_APPEND and not append_file:
            file_mode = FILE_MODE_NEW
            append_file = ""
        out.append(
            {
                "name": name,
                "path": path,
                "auto_paste": bool(item.get("auto_paste", False)),
                "file_mode": file_mode,
                "append_file": append_file,
            }
        )
    return out
