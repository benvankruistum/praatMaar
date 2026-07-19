"""
Event-journal voor externe tools (hybride brug).

Schrijft append-only JSONL onder `%APPDATA%\\praatMaar\\events\\events.jsonl`.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from config import config_dir
from modules._contract import CycleEvent


def events_dir() -> Path:
    return config_dir() / "events"


def events_journal_path() -> Path:
    return events_dir() / "events.jsonl"


class EventJournal:
    """Thread-safe JSONL-schrijver voor dicteercyclus-events."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or events_journal_path()
        self._lock = threading.Lock()

    def write(self, event: CycleEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
