"""Tests for Meeting Buddy agenda dialog."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from modules._builtin.meeting_buddy.agenda_dialog import (
    AgendaDialogResult,
    can_start_meeting,
    library_sections,
    show_agenda_dialog,
)


def test_agenda_dialog_result_fields() -> None:
    result = AgendaDialogResult(
        agenda_text="Budget\nPlanning",
        path=Path("/tmp/Budget.md"),
        start=True,
    )
    assert result.agenda_text == "Budget\nPlanning"
    assert result.path == Path("/tmp/Budget.md")
    assert result.start is True


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
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()

    original_topllevel = tk.Toplevel

    def patched_topllevel(*args, **kwargs):
        dlg = original_topllevel(*args, **kwargs)
        cancel_handler = None
        original_protocol = dlg.protocol

        def protocol(name, handler):
            nonlocal cancel_handler
            if name == "WM_DELETE_WINDOW":
                cancel_handler = handler
            return original_protocol(name, handler)

        dlg.protocol = protocol

        def wait_window():
            if cancel_handler is not None:
                cancel_handler()

        dlg.wait_window = wait_window
        return dlg

    monkeypatch.setattr(tk, "Toplevel", patched_topllevel)

    result = show_agenda_dialog(
        agenda_text="",
        path=None,
        app_dir=Path("/tmp/app"),
        mode="start",
        parent=root,
    )
    root.destroy()
    assert result is None
