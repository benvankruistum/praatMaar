"""Contract tests voor dicteercyclus-events."""

from __future__ import annotations

from modules._contract import SCHEMA_VERSION, CycleEvent, CycleEventType


def test_cycle_event_to_dict_includes_schema_version() -> None:
    event = CycleEvent(
        type=CycleEventType.CYCLE_STARTED,
        session_id="abc-123",
        language="nl",
        mode="toggle",
    )
    data = event.to_dict()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["type"] == "cycle.started"
    assert data["session_id"] == "abc-123"
    assert data["language"] == "nl"
    assert data["mode"] == "toggle"


def test_cycle_event_omits_empty_optional_fields() -> None:
    event = CycleEvent(
        type=CycleEventType.CYCLE_IDLE,
        session_id="x",
    )
    data = event.to_dict()
    assert "transcript" not in data
    assert "path" not in data
