"""Busy feedback while processing (FR-UX-03)."""

from __future__ import annotations

from types import SimpleNamespace

import dictation
from indicator import RecordingState
from indicator._contract import drain_status_queue


def test_signal_processing_busy_notifies_and_tray(monkeypatch) -> None:
    drain_status_queue()
    busy_calls: list[str] = []
    tray = SimpleNamespace(signal_busy=lambda: busy_calls.append("busy"))
    monkeypatch.setattr(dictation, "_tray", tray)
    monkeypatch.setattr(dictation, "MODE", "toggle")

    dictation._signal_processing_busy()

    items = drain_status_queue()
    assert items == [(RecordingState.TRANSCRIBING, "toggle", "")]
    assert busy_calls == ["busy"]
