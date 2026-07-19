"""Tests voor het gedeelde indicator-contract (geen GUI)."""

from __future__ import annotations

from indicator import RecordingState, notify_state, push_level, reset_levels
from indicator._contract import (
    DestinationPillModel,
    destination_display_name,
    drain_status_queue,
    snapshot_levels,
)


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


def test_destination_display_name_truncates() -> None:
    assert destination_display_name(None) == ""
    assert destination_display_name("  kort  ") == "kort"
    long = "a" * 40
    shown = destination_display_name(long)
    assert shown.endswith("…")
    assert len(shown) == 24


def test_destination_pill_visible_when_active() -> None:
    model = DestinationPillModel()
    assert not model.idle_visible
    model.set_destination("Boodschappen")
    assert model.idle_visible
    assert model.name == "Boodschappen"


def test_destination_pill_dismiss_hides_but_keeps_name() -> None:
    model = DestinationPillModel()
    model.set_destination("Notities")
    model.dismiss()
    assert not model.idle_visible
    assert model.name == "Notities"


def test_destination_pill_reshown_on_recording_started() -> None:
    model = DestinationPillModel()
    model.set_destination("Werk")
    model.dismiss()
    model.on_recording_started()
    assert model.idle_visible
    assert model.name == "Werk"


def test_destination_pill_reshown_on_set_destination() -> None:
    model = DestinationPillModel()
    model.set_destination("A")
    model.dismiss()
    model.set_destination("A")  # opnieuw dezelfde ook
    assert model.idle_visible
    model.dismiss()
    model.set_destination("B")
    assert model.idle_visible
    assert model.name == "B"


def test_destination_pill_clear_hides() -> None:
    model = DestinationPillModel()
    model.set_destination("X")
    model.set_destination(None)
    assert not model.idle_visible
    assert model.name is None


def test_destination_pill_dismiss_noop_without_destination() -> None:
    model = DestinationPillModel()
    model.dismiss()
    assert not model.idle_visible
