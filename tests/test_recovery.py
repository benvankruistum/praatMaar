"""Tests voor recovery-transcripts en prune."""

from __future__ import annotations

from pathlib import Path

import recovery


def _patch_dirs(tmp_path: Path, monkeypatch) -> None:
    # recovery importeert `config_dir` by name; patch de gebonden referentie.
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)


def test_save_transcript_and_prune(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    path = recovery.save_transcript("hallo wereld")
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == "hallo wereld"
    assert path.parent == tmp_path / "transcripts"


def test_prune_keeps_newest(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    directory = tmp_path / "transcripts"
    directory.mkdir()
    for index in range(5):
        (directory / f"2026-01-0{index + 1}_120000.txt").write_text(
            str(index), encoding="utf-8"
        )
    recovery.prune_transcripts(max_files=2)
    remaining = sorted(p.name for p in directory.glob("*.txt"))
    assert remaining == ["2026-01-04_120000.txt", "2026-01-05_120000.txt"]


def test_save_transcript_custom_dir_skips_prune(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    monkeypatch.setattr(recovery, "MAX_TRANSCRIPTS", 2)
    custom = tmp_path / "project"
    path = recovery.save_transcript("hallo", directory=custom)
    assert path.parent == custom
    assert path.read_text(encoding="utf-8") == "hallo"

    default = tmp_path / "transcripts"
    default.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        (default / f"2026-01-0{index + 1}_120000.txt").write_text(
            str(index), encoding="utf-8"
        )

    path2 = recovery.save_transcript("tweede", directory=custom)
    assert path2.parent == custom
    assert path2.read_text(encoding="utf-8") == "tweede"
    assert len(list(default.glob("*.txt"))) == 3
    assert path.exists()
    assert len(list(custom.glob("*.txt"))) == 2

    recovery.save_transcript("derde")
    assert len(list(default.glob("*.txt"))) == 2


def test_preserve_audio_moves_wav(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    source = tmp_path / "tmp_audio.wav"
    source.write_bytes(b"RIFF....")
    kept = recovery.preserve_audio(source)
    assert kept.is_file()
    assert kept.suffix == ".wav"
    assert kept.parent == tmp_path / "recovery"
    assert not source.exists()
