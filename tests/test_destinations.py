import sys
from pathlib import Path
from unittest.mock import patch

import destinations as d


def test_normalize_strips_punct_and_case():
    assert d.normalize_phrase("  Boodschappenlijst! ") == "boodschappenlijst"
    assert d.normalize_phrase("Hallo, wereld.") == "hallo wereld"


def test_match_set_exact():
    dests = [{"name": "Boodschappenlijst", "path": "D:/x"}]
    assert d.match_command("boodschappenlijst", dests) == ("set", "Boodschappenlijst")


def test_match_reset():
    assert d.match_command("Standaard!", []) == ("reset", None)
    assert d.match_command("default", []) == ("reset", None)
    assert d.match_command("Standard", []) == ("reset", None)


def test_match_none_for_content():
    dests = [{"name": "notities", "path": "D:/n"}]
    assert d.match_command("notities melk kopen", dests) == ("none", None)


def test_resolve_active_and_default(tmp_path: Path):
    dests = [{"name": "notities", "path": str(tmp_path / "n")}]
    assert d.resolve_save_dir("notities", dests, tmp_path / "default") == tmp_path / "n"
    assert d.resolve_save_dir(None, dests, tmp_path / "default") == tmp_path / "default"


def test_is_reserved_name():
    assert d.is_reserved_name("standaard")
    assert d.is_reserved_name("  Standaard! ")
    assert d.is_reserved_name("default")
    assert d.is_reserved_name("Standard")
    assert not d.is_reserved_name("notities")


def test_find_normalized_collision():
    dests = [
        {"name": "Project-A", "path": "D:/a"},
        {"name": "notities", "path": "D:/n"},
    ]
    assert d.find_normalized_collision("project a", dests) == "Project-A"
    assert d.find_normalized_collision("Project-A", dests, exclude_index=0) is None
    assert d.find_normalized_collision("uniek", dests) is None


def test_sanitize_drops_reserved_and_normalized_duplicates(tmp_path: Path):
    raw = [
        {"name": "Standaard", "path": str(tmp_path / "s")},
        {"name": "Project-A", "path": str(tmp_path / "a")},
        {"name": "project a", "path": str(tmp_path / "b")},
        {"name": "notities", "path": str(tmp_path / "n")},
    ]
    assert d.sanitize_destinations(raw) == [
        {
            "name": "Project-A",
            "path": str(tmp_path / "a"),
            "auto_paste": False,
            "file_mode": "new",
            "append_file": "",
        },
        {
            "name": "notities",
            "path": str(tmp_path / "n"),
            "auto_paste": False,
            "file_mode": "new",
            "append_file": "",
        },
    ]


def test_sanitize_preserves_auto_paste(tmp_path: Path):
    raw = [
        {"name": "a", "path": str(tmp_path / "a"), "auto_paste": True},
        {"name": "b", "path": str(tmp_path / "b")},
    ]
    assert d.sanitize_destinations(raw) == [
        {
            "name": "a",
            "path": str(tmp_path / "a"),
            "auto_paste": True,
            "file_mode": "new",
            "append_file": "",
        },
        {
            "name": "b",
            "path": str(tmp_path / "b"),
            "auto_paste": False,
            "file_mode": "new",
            "append_file": "",
        },
    ]


def test_resolve_auto_paste():
    dests = [
        {"name": "notes", "path": "D:/n", "auto_paste": False},
        {"name": "chat", "path": "D:/c", "auto_paste": True},
    ]
    assert d.resolve_auto_paste(None, dests, True) is True
    assert d.resolve_auto_paste(None, dests, False) is False
    assert d.resolve_auto_paste("notes", dests, True) is False
    assert d.resolve_auto_paste("chat", dests, False) is True
    assert d.resolve_auto_paste("missing", dests, True) is True


def test_find_destination_and_append_file(tmp_path: Path):
    dests = [
        {
            "name": "log",
            "path": str(tmp_path),
            "auto_paste": False,
            "file_mode": d.FILE_MODE_APPEND,
            "append_file": str(tmp_path / "notes.txt"),
        }
    ]
    assert d.find_destination("log", dests) == dests[0]
    assert d.find_destination("missing", dests) is None
    assert d.resolve_file_mode(dests[0]) == d.FILE_MODE_APPEND
    assert d.resolve_append_file(dests[0]) == tmp_path / "notes.txt"
    assert d.resolve_append_file(dests[0] | {"append_file": ""}) is None


def test_sanitize_append_requires_file(tmp_path: Path):
    raw = [
        {
            "name": "log",
            "path": str(tmp_path),
            "file_mode": d.FILE_MODE_APPEND,
            "append_file": "",
        }
    ]
    assert d.sanitize_destinations(raw) == [
        {
            "name": "log",
            "path": str(tmp_path),
            "auto_paste": False,
            "file_mode": "new",
            "append_file": "",
        }
    ]


def test_open_in_explorer_uses_resolved_path(tmp_path: Path, monkeypatch):
    target = tmp_path / "transcripts"
    opened: list[Path] = []

    if sys.platform == "win32":
        monkeypatch.setattr(d.os, "startfile", lambda path: opened.append(Path(path)))
        d.open_in_explorer(target)
    else:
        monkeypatch.setattr(d.sys, "platform", "darwin")

        def fake_run(args, check=False):  # noqa: ARG001
            opened.append(Path(args[1]))
            return None

        with patch.object(d.subprocess, "run", fake_run):
            d.open_in_explorer(target)

    assert target.is_dir()
    assert opened == [target.resolve()]
