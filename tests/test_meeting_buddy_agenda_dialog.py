"""Tests for Meeting Buddy agenda dialog."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from modules._builtin.meeting_buddy.agenda_dialog import (
    AgendaDialogResult,
    can_start_meeting,
    capture_setup_platform,
    library_sections,
    show_agenda_dialog,
)


def test_agenda_dialog_result_fields() -> None:
    result = AgendaDialogResult(
        agenda_text="Budget\nPlanning",
        path=Path("/tmp/Budget.md"),
        start=True,
        enable_loopback=True,
        loopback_device=3,
    )
    assert result.agenda_text == "Budget\nPlanning"
    assert result.path == Path("/tmp/Budget.md")
    assert result.start is True
    assert result.enable_loopback is True
    assert result.loopback_device == 3


def test_capture_setup_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("modules._builtin.meeting_buddy.agenda_dialog.sys.platform", "win32")
    assert capture_setup_platform() == "windows"
    monkeypatch.setattr("modules._builtin.meeting_buddy.agenda_dialog.sys.platform", "darwin")
    assert capture_setup_platform() == "macos"
    monkeypatch.setattr("modules._builtin.meeting_buddy.agenda_dialog.sys.platform", "linux")
    assert capture_setup_platform() == "other"


def test_agenda_dialog_result_is_frozen() -> None:
    result = AgendaDialogResult(agenda_text="", path=None, start=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.start = True  # type: ignore[misc]


def test_module_exports_show_agenda_dialog() -> None:
    assert callable(show_agenda_dialog)


def test_can_start_meeting_true_when_topics_present() -> None:
    assert can_start_meeting("Budget\n- Planning") is True


def test_can_start_meeting_false_when_empty() -> None:
    assert can_start_meeting("") is False
    assert can_start_meeting("   \n") is False


def test_library_sections_includes_recent_then_all() -> None:
    recent = [Path("/a/recent.md")]
    all_agendas = [Path("/a/recent.md"), Path("/a/other.md")]
    sections = library_sections(recent=recent, all_agendas=all_agendas)
    assert sections == [("recent", recent), ("all", all_agendas)]


def test_library_sections_all_only_when_no_recent() -> None:
    all_agendas = [Path("/a/other.md")]
    sections = library_sections(recent=[], all_agendas=all_agendas)
    assert sections == [("all", all_agendas)]


def test_show_agenda_dialog_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    result = show_agenda_dialog(
        agenda_text="",
        path=None,
        app_dir=Path("/tmp/app"),
        mode="start",
    )
    assert result is None


def test_library_rerender_does_not_accumulate_widgets(tmp_path: Path) -> None:
    # Zelfde bugklasse als in de overlay (recursieve _clear_layout): elke
    # bibliotheek-refresh moet de vorige rijen vrijgeven, ook de geneste.
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QLabel

    from modules._builtin.meeting_buddy.agenda_dialog import _AgendaDialog
    from ui.app import ensure_app

    app = ensure_app([])
    (tmp_path / "agendas").mkdir(parents=True, exist_ok=True)
    (tmp_path / "agendas" / "overleg.md").write_text("# Overleg\n- Budget\n", encoding="utf-8")

    dialog = _AgendaDialog(parent=None, agenda_text="", path=None, app_dir=tmp_path, mode="start")
    try:
        dialog._populate_library()
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        first = len(dialog._library_pane.findChildren(QLabel))

        for _ in range(3):
            dialog._populate_library()
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        assert len(dialog._library_pane.findChildren(QLabel)) == first
    finally:
        dialog.close()
