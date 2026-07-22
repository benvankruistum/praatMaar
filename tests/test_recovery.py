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
        (directory / f"2026-01-0{index + 1}_120000.txt").write_text(str(index), encoding="utf-8")
    recovery.prune_transcripts(max_files=2)
    remaining = sorted(p.name for p in directory.glob("*.txt"))
    assert remaining == ["2026-01-04_120000.txt", "2026-01-05_120000.txt"]


def test_append_transcript_adds_timestamp(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    path = recovery.append_transcript("eerste regel", target)
    assert path == target
    content = target.read_text(encoding="utf-8")
    assert content.endswith("eerste regel\n")
    assert "\n\n" in content or content.count("\n") >= 2

    recovery.append_transcript("tweede regel", target)
    content = target.read_text(encoding="utf-8")
    assert "tweede regel" in content
    assert content.count("eerste regel") == 1


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
        (default / f"2026-01-0{index + 1}_120000.txt").write_text(str(index), encoding="utf-8")

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


def test_list_recovery_wavs_newest_first(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    directory = tmp_path / "recovery"
    directory.mkdir()
    older = directory / "2026-01-01_120000.wav"
    newer = directory / "2026-01-02_120000.wav"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    import os

    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_700_000_100, 1_700_000_100))
    listed = recovery.list_recovery_wavs()
    assert [p.name for p in listed] == ["2026-01-02_120000.wav", "2026-01-01_120000.wav"]


def test_list_recovery_wavs_empty_dir(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    assert recovery.list_recovery_wavs() == []


def test_delete_recovery_file(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    directory = tmp_path / "recovery"
    directory.mkdir()
    target = directory / "2026-01-01_120000.wav"
    target.write_bytes(b"x")
    recovery.delete_recovery_file(target)
    assert not target.exists()


def test_delete_recovery_file_rejects_outside(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    (tmp_path / "recovery").mkdir()
    outsider = tmp_path / "other.wav"
    outsider.write_bytes(b"x")
    try:
        recovery.delete_recovery_file(outsider)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert outsider.exists()


def test_delete_all_recovery_files(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    directory = tmp_path / "recovery"
    directory.mkdir()
    (directory / "a.wav").write_bytes(b"1")
    (directory / "b.wav").write_bytes(b"2")
    (directory / "note.txt").write_text("x", encoding="utf-8")
    assert recovery.delete_all_recovery_files() == 2
    assert list(directory.glob("*.wav")) == []
    assert (directory / "note.txt").exists()


def test_format_size_and_label(tmp_path: Path, monkeypatch) -> None:
    _patch_dirs(tmp_path, monkeypatch)
    assert recovery.format_size(500) == "500 B"
    assert recovery.format_size(2048) == "2.0 KB"
    assert recovery.format_size(2 * 1024 * 1024) == "2.0 MB"
    directory = tmp_path / "recovery"
    directory.mkdir()
    path = directory / "2026-01-01_120000.wav"
    path.write_bytes(b"abcd")
    assert recovery.recovery_list_label(path) == "2026-01-01_120000.wav  (4 B)"
