"""Discrete file-transcript save: file_ prefix, nooit append."""

from __future__ import annotations

from pathlib import Path

import recovery
from app.recovery_actions import save_transcript_discrete, save_transcript_routed


def _patch_dirs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)


def test_save_transcript_discrete_uses_file_prefix(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    dest_dir = tmp_path / "notulen"
    dest_dir.mkdir()
    path = save_transcript_discrete(
        "tekst",
        active_destination="Notulen",
        destinations_list=[{"name": "Notulen", "path": str(dest_dir)}],
    )
    assert path.parent == dest_dir
    assert path.read_text(encoding="utf-8") == "tekst"
    assert path.name.startswith("file_")
    assert path.suffix == ".txt"
    assert recovery.parse_transcript_stem(path.stem) is None


def test_save_transcript_discrete_ignores_append_file(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    dest_dir = tmp_path / "logmap"
    dest_dir.mkdir()
    append_file = dest_dir / "log.txt"
    append_file.write_text("bestaand\n", encoding="utf-8")
    dests = [
        {
            "name": "Log",
            "path": str(dest_dir),
            "file_mode": "append",
            "append_file": str(append_file),
        }
    ]
    routed = save_transcript_routed(
        "via append",
        active_destination="Log",
        destinations_list=dests,
    )
    assert routed == append_file
    discrete = save_transcript_discrete(
        "via file job",
        active_destination="Log",
        destinations_list=dests,
    )
    assert discrete != append_file
    assert discrete.parent == dest_dir
    assert discrete.name.startswith("file_")
    assert append_file.read_text(encoding="utf-8").endswith("via append\n")
    assert "via file job" not in append_file.read_text(encoding="utf-8")
    assert discrete.read_text(encoding="utf-8") == "via file job"
