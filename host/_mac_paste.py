"""Quartz Cmd+V paste for the macOS Host adapter.

Kept behind the ``host`` seam so paste does not depend on a root-level
``mac_input`` module. Uses CGEvents (not pyautogui/pynput) to avoid TSM
crashes on macOS 26+ from non-main threads.
"""

from __future__ import annotations

_KEY_V = 0x09


def paste_command_v() -> None:
    """Stuurt ⌘V via Quartz CGEvents (geen TSM / geen pyautogui)."""

    from Quartz import (  # type: ignore[import-not-found]
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )

    down = CGEventCreateKeyboardEvent(None, _KEY_V, True)
    up = CGEventCreateKeyboardEvent(None, _KEY_V, False)
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)
