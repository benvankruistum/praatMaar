"""Tests voor ModuleBus — dispatch en foutisolatie."""

from __future__ import annotations

from pathlib import Path

from modules._contract import CycleEvent, CycleEventType, ModuleContext
from modules.bus import ModuleBus
from modules.journal import EventJournal


class FailingModule:
    id = "fail"

    def display_name_key(self) -> str:
        return "modules.fail.name"

    def description_key(self) -> str:
        return "modules.fail.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        pass

    def on_event(self, event: CycleEvent) -> None:
        raise RuntimeError("boom")


class RecordingModule:
    id = "recorder"

    def __init__(self) -> None:
        self.events: list[CycleEvent] = []

    def display_name_key(self) -> str:
        return "modules.recorder.name"

    def description_key(self) -> str:
        return "modules.recorder.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        pass

    def on_event(self, event: CycleEvent) -> None:
        self.events.append(event)


def test_bus_dispatches_to_modules_and_journal(tmp_path: Path) -> None:
    journal_path = tmp_path / "events.jsonl"
    journal = EventJournal(path=journal_path)
    recorder = RecordingModule()
    bus = ModuleBus(journal=journal, modules=[FailingModule(), recorder])

    event = CycleEvent(type=CycleEventType.CYCLE_STARTED, session_id="s1")
    bus.emit(event)

    assert recorder.events == [event]
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"cycle.started"' in lines[0]
