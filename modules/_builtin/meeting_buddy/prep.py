"""Preparation helpers for Meeting Buddy sessions."""

from __future__ import annotations

import re

_AGENDA_PREFIX = re.compile(r"^\s*(?:(?:\d+[.)])|[-*•])\s*")


def parse_agenda(text: str) -> list[str]:
    """Return non-empty agenda lines without common bullet prefixes."""

    items: list[str] = []
    for line in text.splitlines():
        item = _AGENDA_PREFIX.sub("", line).strip()
        if item:
            items.append(item)
    return items
