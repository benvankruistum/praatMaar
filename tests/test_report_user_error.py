"""Non-modal mic/user error path (FR-UX-01)."""

from __future__ import annotations

from types import SimpleNamespace

import dictation


def test_report_user_error_sets_attention_without_modal(monkeypatch) -> None:
    attention: list[bool] = []
    modal_calls: list[tuple] = []

    tray = SimpleNamespace(
        set_attention_needed=lambda needed, **_kwargs: attention.append(bool(needed))
    )
    monkeypatch.setattr(dictation, "_tray", tray)
    monkeypatch.setattr(dictation, "_indicator", SimpleNamespace())

    def boom_error(*args, **kwargs) -> None:
        modal_calls.append((args, kwargs))

    monkeypatch.setattr("ui.dialogs.message.error", boom_error)

    dictation._report_user_error("No Default Input Device Available")

    assert attention == [True]
    assert modal_calls == []


def test_report_user_error_works_without_indicator(monkeypatch) -> None:
    attention: list[bool] = []
    tray = SimpleNamespace(
        set_attention_needed=lambda needed, **_kwargs: attention.append(bool(needed))
    )
    monkeypatch.setattr(dictation, "_tray", tray)
    monkeypatch.setattr(dictation, "_indicator", None)

    dictation._report_user_error("mic missing")
    assert attention == [True]
