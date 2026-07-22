"""Meeting Buddy agenda files (``.md``) and recent-list helpers."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from modules.settings_store import load_config, module_dir, save_config

_MODULE_ID = "meeting-buddy"
_RECENTS_KEY = "agenda_recents"
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def agendas_dir(app_dir: Path) -> Path:
    """Directory for library agenda markdown files."""

    return module_dir(app_dir, _MODULE_ID) / "agendas"


def display_title(path: Path, text: str | None = None) -> str:
    """Return display name: optional ``#`` heading, else filename stem."""

    raw = text if text is not None else (path.read_text(encoding="utf-8") if path.is_file() else "")
    heading, _body = parse_agenda_markdown(raw)
    if heading:
        return heading
    return path.stem


def parse_agenda_markdown(text: str) -> tuple[str | None, str]:
    """Split optional leading H1 from agenda body text."""

    stripped = text.lstrip("\ufeff")
    match = _H1_RE.match(stripped)
    if not match:
        return None, text.strip("\n") + ("\n" if text.strip() else "")
    heading = match.group(1).strip()
    rest = stripped[match.end() :].lstrip("\n")
    body = rest.strip("\n")
    return heading, (body + "\n") if body else ""


def format_agenda_markdown(*, title: str | None, body: str) -> str:
    """Serialize body with optional ``# title`` line."""

    clean_body = body.strip("\n")
    if title:
        if clean_body:
            return f"# {title}\n\n{clean_body}\n"
        return f"# {title}\n"
    return (clean_body + "\n") if clean_body else ""


def list_agendas(app_dir: Path) -> list[Path]:
    """Sorted ``.md`` files in the library folder."""

    directory = agendas_dir(app_dir)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".md")


def load_agenda(path: Path) -> tuple[str, str]:
    """Load ``(display_title, body)`` from a markdown file."""

    text = path.read_text(encoding="utf-8")
    return display_title(path, text), parse_agenda_markdown(text)[1]


def save_agenda(path: Path, body: str, *, title: str | None = None) -> Path:
    """Write agenda markdown; create parent dirs. Returns ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve existing H1 unless an explicit title is provided.
    existing_title: str | None = None
    if title is None and path.is_file():
        existing_title, _ = parse_agenda_markdown(path.read_text(encoding="utf-8"))
    heading = title if title is not None else existing_title
    path.write_text(format_agenda_markdown(title=heading, body=body), encoding="utf-8")
    return path


def default_new_path(app_dir: Path, body: str) -> Path:
    """Suggest a new library path from the first topic line or today's date."""

    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    stem = _safe_stem(first) if first else f"agenda-{date.today().strftime('%Y%m%d')}"
    return agendas_dir(app_dir) / f"{stem}.md"


def list_recent(app_dir: Path, *, limit: int = 8) -> list[Path]:
    """Recent agenda paths that still exist, newest first."""

    raw = load_config(app_dir, _MODULE_ID).get(_RECENTS_KEY, [])
    if not isinstance(raw, list):
        return []
    result: list[Path] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        path = Path(item)
        if path.is_file():
            result.append(path)
        if len(result) >= limit:
            break
    return result


def touch_recent(app_dir: Path, path: Path, *, limit: int = 8) -> None:
    """Move ``path`` to the front of the recent list and persist."""

    resolved = str(path.resolve())
    current = load_config(app_dir, _MODULE_ID)
    raw = current.get(_RECENTS_KEY, [])
    previous = [item for item in raw if isinstance(item, str) and item != resolved]
    current[_RECENTS_KEY] = [resolved, *previous][:limit]
    save_config(app_dir, _MODULE_ID, current)


def _safe_stem(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]', "", text).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:80] or "agenda").strip()
