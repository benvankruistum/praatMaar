"""
Inbox-mirror module — kopieert opgeslagen transcripts naar een vaste inbox-map.

Handig voor externe tools die `%APPDATA%\\praatMaar\\inbox\\` kunnen volgen.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from modules._contract import CycleEvent, CycleEventType, ModuleContext


class InboxMirrorModule:
    id = "inbox-mirror"

    def __init__(self) -> None:
        self._inbox_dir: Path | None = None

    def display_name_key(self) -> str:
        return "modules.inbox_mirror.name"

    def description_key(self) -> str:
        return "modules.inbox_mirror.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._inbox_dir = ctx.app_dir / "inbox"
        self._inbox_dir.mkdir(parents=True, exist_ok=True)

    def on_event(self, event: CycleEvent) -> None:
        if event.type != CycleEventType.TRANSCRIPT_SAVED or not event.path:
            return
        if self._inbox_dir is None:
            return

        source = Path(event.path)
        if not source.is_file():
            return

        target = self._inbox_dir / source.name
        if target.exists():
            stem = source.stem
            suffix = source.suffix
            counter = 2
            while target.exists():
                target = self._inbox_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(source, target)
