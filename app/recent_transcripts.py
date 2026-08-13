"""Recente-transcripts tray/pill-menu helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import destinations
import i18n
import recovery
from app.clipboard import copy_to_clipboard


def recent_transcript_search_dirs(destinations_list: list[dict[str, Any]]) -> list[Path]:
    """Default transcripts-map plus directory-bestemmingen (geen append)."""

    dirs: list[Path] = [recovery.transcripts_dir()]
    seen: set[str] = set()
    try:
        seen.add(str(dirs[0].resolve()))
    except OSError:
        seen.add(str(dirs[0]))
    for path in destinations.directory_save_paths(destinations_list):
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(path)
    return dirs


def copy_recent_transcript_to_clipboard(
    path: Path,
    *,
    pyperclip_mod: Any | None,
    ui_dispatch: Callable,
) -> None:
    """Zet een bewaard transcript opnieuw op het klembord (geen plakken)."""

    try:
        text = recovery.read_transcript_text(path)
    except OSError as exc:
        print(i18n.t("rec.clipboard_warn", error=exc))
        return
    try:
        copy_to_clipboard(text, pyperclip_mod=pyperclip_mod, ui_dispatch=ui_dispatch)
        print(i18n.t("rec.clipboard"))
    except Exception as exc:
        print(i18n.t("rec.clipboard_warn", error=exc))


def recent_transcript_menu_entries(
    destinations_list: list[dict[str, Any]],
    *,
    pyperclip_mod: Any | None,
    ui_dispatch: Callable,
) -> list[tuple]:
    """Tray/pill-submenu: max. 5 recente timestamp-transcripts of empty state."""

    items = recovery.list_recent_transcripts(recent_transcript_search_dirs(destinations_list))
    if not items:
        return [("disabled", i18n.t("tray.recent_transcripts.empty"))]
    entries: list[tuple] = []
    language = i18n.ui_language()
    for item in items:
        label = recovery.format_recent_transcript_label(item, language)
        path = item.path
        entries.append(
            (
                "item",
                label,
                lambda p=path: copy_recent_transcript_to_clipboard(
                    p, pyperclip_mod=pyperclip_mod, ui_dispatch=ui_dispatch
                ),
            )
        )
    return entries
