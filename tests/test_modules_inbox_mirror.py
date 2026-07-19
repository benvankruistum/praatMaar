"""Tests voor inbox-spiegel module."""

from __future__ import annotations

from pathlib import Path

from modules._builtin.inbox_mirror import InboxMirrorModule
from modules._contract import CycleEvent, CycleEventType, ModuleContext


def test_inbox_mirror_copies_saved_transcript(tmp_path: Path) -> None:
    source_dir = tmp_path / "transcripts"
    source_dir.mkdir()
    transcript = source_dir / "2026-07-19_120000.txt"
    transcript.write_text("hallo wereld", encoding="utf-8")

    module = InboxMirrorModule()
    module.on_app_start(ModuleContext(app_dir=tmp_path))

    module.on_event(
        CycleEvent(
            type=CycleEventType.TRANSCRIPT_SAVED,
            session_id="s1",
            path=str(transcript),
            transcript="hallo wereld",
        )
    )

    copied = tmp_path / "inbox" / transcript.name
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "hallo wereld"
