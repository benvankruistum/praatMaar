"""Helpers for routing pill/hotkey stop to an active Meeting Buddy session."""

from __future__ import annotations

from typing import Any, Protocol


class _MeetingStoppable(Protocol):
    id: str

    @property
    def is_session_active(self) -> bool: ...

    def stop_meeting(self) -> None: ...


def stop_active_meeting(modules: list[Any]) -> bool:
    """Stop the first active Meeting Buddy session. Return True if one was stopped."""

    for module in modules:
        if getattr(module, "id", None) != "meeting-buddy":
            continue
        is_active = getattr(module, "is_session_active", None)
        if callable(is_active):
            active = bool(is_active())
        else:
            active = bool(is_active)
        if not active:
            return False
        stop = getattr(module, "stop_meeting", None)
        if not callable(stop):
            return False
        stop()
        return True
    return False
