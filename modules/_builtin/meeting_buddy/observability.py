"""Privacy-safe local observability for Meeting Buddy."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

_LOG = logging.getLogger("praatmaar.meeting_buddy")


class EventObserver(Protocol):
    """Receives one sanitized structured event."""

    def record(self, event: Mapping[str, Any]) -> None: ...


class RecordingObserver:
    """In-memory observer used by tests and diagnostics."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    @property
    def names(self) -> list[str]:
        return [str(event["name"]) for event in self.events]

    def record(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))


def log_event(
    observer: EventObserver | None,
    name: str,
    **fields: Any,
) -> None:
    """Log an event locally after removing transcript-bearing text fields."""

    event = {"name": name}
    event.update(
        {
            key: value
            for key, value in fields.items()
            if "text" not in key.casefold() and "transcript" not in key.casefold()
        }
    )
    _LOG.debug("Meeting Buddy event: %s", event)
    if name == "capture_sources":
        _LOG.info(
            "Meeting capture sources: mic_device=%s loopback_device=%s "
            "loopback_requested=%s loopback_active=%s",
            fields.get("mic_device"),
            fields.get("loopback_device"),
            fields.get("loopback_requested"),
            fields.get("loopback_active"),
        )
    if observer is not None:
        observer.record(event)
