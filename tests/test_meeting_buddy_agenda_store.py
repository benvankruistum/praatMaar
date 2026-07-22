"""Tests for Meeting Buddy agenda markdown store and recents."""

from __future__ import annotations

from pathlib import Path

from modules._builtin.meeting_buddy import agenda_store as store


def test_display_title_uses_filename_stem(tmp_path: Path) -> None:
    path = tmp_path / "Budgetoverleg.md"
    path.write_text("Opening\n", encoding="utf-8")
    assert store.display_title(path) == "Budgetoverleg"


def test_display_title_prefers_h1_when_present(tmp_path: Path) -> None:
    path = tmp_path / "Budgetoverleg.md"
    text = "# Q3 Budget\n\nOpening\n"
    path.write_text(text, encoding="utf-8")
    assert store.display_title(path, text) == "Q3 Budget"


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    app_dir = tmp_path
    path = store.agendas_dir(app_dir) / "MT-overleg.md"
    store.save_agenda(path, "Opening\nRondvraag\n")
    title, body = store.load_agenda(path)
    assert title == "MT-overleg"
    assert "Opening" in body
    assert "Rondvraag" in body


def test_list_agendas_only_md(tmp_path: Path) -> None:
    agendas = store.agendas_dir(tmp_path)
    agendas.mkdir(parents=True)
    (agendas / "a.md").write_text("A\n", encoding="utf-8")
    (agendas / "b.txt").write_text("B\n", encoding="utf-8")
    names = [p.name for p in store.list_agendas(tmp_path)]
    assert names == ["a.md"]


def test_touch_recent_orders_and_limits(tmp_path: Path) -> None:
    agendas = store.agendas_dir(tmp_path)
    paths = []
    for name in ("a.md", "b.md", "c.md"):
        p = agendas / name
        store.save_agenda(p, f"{name}\n")
        paths.append(p)

    store.touch_recent(tmp_path, paths[0], limit=2)
    store.touch_recent(tmp_path, paths[1], limit=2)
    store.touch_recent(tmp_path, paths[2], limit=2)
    recent = store.list_recent(tmp_path, limit=2)
    assert [p.name for p in recent] == ["c.md", "b.md"]


def test_list_recent_drops_missing_files(tmp_path: Path) -> None:
    path = store.agendas_dir(tmp_path) / "gone.md"
    store.save_agenda(path, "X\n")
    store.touch_recent(tmp_path, path)
    path.unlink()
    assert store.list_recent(tmp_path) == []


def test_default_new_path_from_first_topic(tmp_path: Path) -> None:
    path = store.default_new_path(tmp_path, "Welkomstwoord\nGraph\n")
    assert path.name == "Welkomstwoord.md"
    assert path.parent == store.agendas_dir(tmp_path)
