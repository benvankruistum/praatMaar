"""Throttled UI dispatch for Meeting Buddy state snapshots."""

from __future__ import annotations

import time
from collections.abc import Callable

from .state import MeetingState

UiUpdate = Callable[[MeetingState], None]


class MeetingUiPresenter:
    """Rate-limit overlay updates while allowing forced refreshes."""

    def __init__(self, on_ui_update: UiUpdate | None = None) -> None:
        self._on_ui_update = on_ui_update or (lambda _state: None)
        self._last_notify_at = 0.0

    def notify(self, state: MeetingState | None, *, force: bool = False) -> None:
        if state is None:
            return
        if not force:
            now = time.monotonic()
            if now - self._last_notify_at < 0.5:
                return
            self._last_notify_at = now
        else:
            self._last_notify_at = time.monotonic()
        self._on_ui_update(state)
