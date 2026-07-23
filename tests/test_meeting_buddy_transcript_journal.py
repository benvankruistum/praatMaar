"""Tests for Meeting Buddy streaming transcript journal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules._builtin.meeting_buddy import transcript_journal as journal
from modules._builtin.meeting_buddy.state import Topic, TopicSource, TopicStatus


def test_transcripts_dir(tmp_path: Path) -> None:
    assert journal.transcripts_dir(tmp_path) == tmp_path / "meeting-buddy" / "transcripts"


def test_create_writes_header_and_transcript_section(tmp_path: Path) -> None:
    started = datetime(2026, 7, 22, 21, 5)
    doc = journal.TranscriptJournal.create(
        tmp_path,
        title="MT-overleg",
        agenda_titles=["Opening", "Rondvraag"],
        started_at=started,
    )
    text = doc.path.read_text(encoding="utf-8")
    assert doc.path.parent == journal.transcripts_dir(tmp_path)
    assert doc.path.name.startswith("2026-07-22_2105_")
    assert "MT-overleg" in doc.path.name
    assert text.startswith("# MT-overleg\n")
    assert "Status: lopend" in text
    assert "- [ ] Opening" in text
    assert "- [ ] Rondvraag" in text
    assert "## Transcript\n" in text


def test_append_final_grows_transcript(tmp_path: Path) -> None:
    doc = journal.TranscriptJournal.create(
        tmp_path,
        title="Demo",
        agenda_titles=["A"],
        started_at=datetime(2026, 7, 22, 10, 0),
    )
    doc.append_final("Hallo")
    doc.append_final("wereld")
    body = doc.path.read_text(encoding="utf-8").split("## Transcript\n", 1)[1]
    assert "Hallo" in body
    assert "wereld" in body


def test_append_final_ignores_blank(tmp_path: Path) -> None:
    doc = journal.TranscriptJournal.create(
        tmp_path,
        title="Demo",
        agenda_titles=[],
        started_at=datetime(2026, 7, 22, 10, 0),
    )
    before = doc.path.read_text(encoding="utf-8")
    doc.append_final("  \n")
    assert doc.path.read_text(encoding="utf-8") == before


def test_finalize_updates_status_and_agenda(tmp_path: Path) -> None:
    doc = journal.TranscriptJournal.create(
        tmp_path,
        title="Demo",
        agenda_titles=["Opening", "Graph"],
        started_at=datetime(2026, 7, 22, 10, 0),
    )
    doc.append_final("tekst")
    ended = datetime(2026, 7, 22, 10, 30)
    topics = (
        Topic(id="1", title="Opening", status=TopicStatus.DISCUSSED, source=TopicSource.AGENDA),
        Topic(id="2", title="Graph", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
    )
    path = doc.finalize(topics=topics, ended_at=ended)
    text = path.read_text(encoding="utf-8")
    assert "Status: gestopt" in text
    assert "Gestopt: 2026-07-22 10:30" in text
    assert "- [x] Opening" in text
    assert "- [ ] Graph" in text
    assert "tekst" in text
