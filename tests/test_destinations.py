from pathlib import Path

import destinations as d


def test_normalize_strips_punct_and_case():
    assert d.normalize_phrase("  Boodschappenlijst! ") == "boodschappenlijst"
    assert d.normalize_phrase("Hallo, wereld.") == "hallo wereld"


def test_match_set_exact():
    dests = [{"name": "Boodschappenlijst", "path": "D:/x"}]
    assert d.match_command("boodschappenlijst", dests) == ("set", "Boodschappenlijst")


def test_match_reset():
    assert d.match_command("Standaard!", []) == ("reset", None)


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
        {"name": "Project-A", "path": str(tmp_path / "a"), "auto_paste": False},
        {"name": "notities", "path": str(tmp_path / "n"), "auto_paste": False},
    ]


def test_sanitize_preserves_auto_paste(tmp_path: Path):
    raw = [
        {"name": "a", "path": str(tmp_path / "a"), "auto_paste": True},
        {"name": "b", "path": str(tmp_path / "b")},
    ]
    assert d.sanitize_destinations(raw) == [
        {"name": "a", "path": str(tmp_path / "a"), "auto_paste": True},
        {"name": "b", "path": str(tmp_path / "b"), "auto_paste": False},
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
