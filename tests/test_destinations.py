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
