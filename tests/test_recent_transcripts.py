"""Tests for recent-transcript listing used by the tray cascade."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import destinations
import recovery


def test_parse_transcript_stem_basic() -> None:
    parsed = recovery.parse_transcript_stem("2026-08-10_143005")
    assert parsed is not None
    recorded_at, collision = parsed
    assert recorded_at == datetime(2026, 8, 10, 14, 30, 5)
    assert collision is None


def test_parse_transcript_stem_collision() -> None:
    parsed = recovery.parse_transcript_stem("2026-08-10_143005_2")
    assert parsed is not None
    _, collision = parsed
    assert collision == 2


def test_parse_transcript_stem_rejects_other_names() -> None:
    assert recovery.parse_transcript_stem("notes") is None
    assert recovery.parse_transcript_stem("2026-08-10") is None
    assert recovery.parse_transcript_stem("meeting-buddy-log") is None


def test_list_recent_transcripts_orders_and_limits(tmp_path: Path) -> None:
    default = tmp_path / "transcripts"
    custom = tmp_path / "project"
    default.mkdir()
    custom.mkdir()
    older = default / "2026-08-01_100000.txt"
    newer = custom / "2026-08-10_120000.txt"
    mid = default / "2026-08-05_090000.txt"
    older.write_text("oud", encoding="utf-8")
    mid.write_text("midden", encoding="utf-8")
    newer.write_text("nieuw", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 30, now - 30))
    os.utime(mid, (now - 20, now - 20))
    os.utime(newer, (now - 10, now - 10))

    items = recovery.list_recent_transcripts([default, custom], limit=2)
    assert [item.path for item in items] == [newer, mid]


def test_list_recent_skips_non_matching_and_missing_dirs(tmp_path: Path) -> None:
    directory = tmp_path / "transcripts"
    directory.mkdir()
    (directory / "2026-08-10_111111.txt").write_text("ok", encoding="utf-8")
    (directory / "readme.txt").write_text("skip", encoding="utf-8")
    missing = tmp_path / "gone"
    items = recovery.list_recent_transcripts([directory, missing], limit=5)
    assert len(items) == 1
    assert items[0].path.name == "2026-08-10_111111.txt"


def test_format_recent_transcript_label_locales() -> None:
    item = recovery.RecentTranscript(
        path=Path("2026-08-10_143005_3.txt"),
        recorded_at=datetime(2026, 8, 10, 14, 30, 5),
        collision_index=3,
        mtime=1.0,
    )
    assert recovery.format_recent_transcript_label(item, "nl") == "10-08-2026 14:30:05 (#3)"
    assert recovery.format_recent_transcript_label(item, "de") == "10.08.2026 14:30:05 (#3)"
    assert recovery.format_recent_transcript_label(item, "en") == "2026-08-10 14:30:05 (#3)"


def test_read_transcript_text(tmp_path: Path) -> None:
    path = tmp_path / "2026-08-10_120000.txt"
    path.write_text("hallo wereld", encoding="utf-8")
    assert recovery.read_transcript_text(path) == "hallo wereld"


def test_directory_save_paths_skips_append(tmp_path: Path) -> None:
    new_dir = tmp_path / "new"
    append_dir = tmp_path / "append"
    items = [
        {
            "name": "Project",
            "path": str(new_dir),
            "file_mode": destinations.FILE_MODE_NEW,
            "append_file": "",
            "auto_paste": False,
        },
        {
            "name": "Log",
            "path": str(append_dir),
            "file_mode": destinations.FILE_MODE_APPEND,
            "append_file": str(append_dir / "log.txt"),
            "auto_paste": False,
        },
        {
            "name": "Project kopie",
            "path": str(new_dir),
            "file_mode": destinations.FILE_MODE_NEW,
            "append_file": "",
            "auto_paste": False,
        },
    ]
    paths = destinations.directory_save_paths(items)
    assert paths == [new_dir]
