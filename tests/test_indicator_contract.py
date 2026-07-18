"""Tests voor het gedeelde indicator-contract (geen GUI)."""

from __future__ import annotations

from indicator import RecordingState, notify_state, push_level, reset_levels
from indicator._contract import drain_status_queue, snapshot_levels


def test_recording_state_values() -> None:
    assert {s.name for s in RecordingState} == {
        "IDLE",
        "RECORDING",
        "TRANSCRIBING",
        "CANCELLED",
        "ERROR",
    }


def test_notify_state_queues() -> None:
    drain_status_queue()
    notify_state(RecordingState.RECORDING, "toggle")
    notify_state(RecordingState.TRANSCRIBING, "ptt")
    items = drain_status_queue()
    assert items == [
        (RecordingState.RECORDING, "toggle"),
        (RecordingState.TRANSCRIBING, "ptt"),
    ]


def test_levels_buffer() -> None:
    reset_levels()
    push_level(0.1)
    push_level(0.2)
    assert snapshot_levels() == [0.1, 0.2]
    reset_levels()
    assert snapshot_levels() == []
