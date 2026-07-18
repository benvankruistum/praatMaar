"""
macOS-toetsenbord via AppKit NSEvent (main thread) — geen pynput.

Op macOS 26+ crasht pynput's Listener: die raakt TSM/HIToolbox vanaf een
achtergrondthread (`dispatch_assert_queue` / SIGTRAP). NSEvent-monitors lopen
op de Cocoa-mainloop (dezelfde als pystray) en vermijden die API.

Paste gebeurt met Quartz CGEvents (⌘V via keycode), niet via pyautogui/pynput.
"""

from __future__ import annotations

from typing import Any, Callable

# ANSI/US keycodes → tokens (fysieke toets; voldoende voor hotkeys + settings).
_KEYCODE_TOKENS: dict[int, str] = {
    0x00: "a",
    0x01: "s",
    0x02: "d",
    0x03: "f",
    0x04: "h",
    0x05: "g",
    0x06: "z",
    0x07: "x",
    0x08: "c",
    0x09: "v",
    0x0B: "b",
    0x0C: "q",
    0x0D: "w",
    0x0E: "e",
    0x0F: "r",
    0x10: "y",
    0x11: "t",
    0x12: "1",
    0x13: "2",
    0x14: "3",
    0x15: "4",
    0x16: "6",
    0x17: "5",
    0x18: "=",
    0x19: "9",
    0x1A: "7",
    0x1B: "-",
    0x1C: "8",
    0x1D: "0",
    0x1E: "]",
    0x1F: "o",
    0x20: "u",
    0x21: "[",
    0x22: "i",
    0x23: "p",
    0x25: "l",
    0x26: "j",
    0x27: "'",
    0x28: "k",
    0x29: ";",
    0x2A: "\\",
    0x2B: ",",
    0x2C: "/",
    0x2D: "n",
    0x2E: "m",
    0x2F: ".",
    0x32: "`",
    0x24: "enter",
    0x30: "tab",
    0x31: "space",
    0x33: "backspace",
    0x35: "esc",
    0x75: "delete",
    0x73: "home",
    0x77: "end",
    0x74: "page_up",
    0x79: "page_down",
    0x7A: "f1",
    0x78: "f2",
    0x63: "f3",
    0x76: "f4",
    0x60: "f5",
    0x61: "f6",
    0x62: "f7",
    0x64: "f8",
    0x65: "f9",
    0x6D: "f10",
    0x67: "f11",
    0x6F: "f12",
}

# Modifier keycodes (FlagsChanged).
_MOD_KEYCODES: dict[int, str] = {
    0x37: "cmd",  # left command
    0x36: "cmd",  # right command
    0x38: "shift",
    0x3C: "shift",
    0x3A: "alt",  # option
    0x3D: "alt",
    0x3B: "ctrl",
    0x3E: "ctrl",
}

_KEY_V = 0x09


class MacKey:
    """Minimale toets voor hotkeys.key_to_token / settings-capture."""

    __slots__ = ("praatmaar_token", "name", "vk", "char")

    def __init__(self, token: str) -> None:
        self.praatmaar_token = token
        self.name = token
        self.vk = None
        self.char = token if len(token) == 1 else None


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


def _token_for_keycode(keycode: int) -> str | None:
    if keycode in _MOD_KEYCODES:
        return _MOD_KEYCODES[keycode]
    return _KEYCODE_TOKENS.get(int(keycode))


class QuartzKeyListener:
    """
    Globale toetsenmonitor op de Cocoa-mainloop.

    API-compatibiliteit met pynput.Listener: `start()` / `stop()`, callbacks
    `on_press` / `on_release` krijgen een `MacKey`.
    """

    def __init__(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None],
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._monitor: Any = None
        self._mod_down: set[str] = set()

    def start(self) -> None:
        if self._monitor is not None:
            return

        from AppKit import (  # type: ignore[import-not-found]
            NSEvent,
            NSEventMaskFlagsChanged,
            NSEventMaskKeyDown,
            NSEventMaskKeyUp,
        )

        mask = NSEventMaskKeyDown | NSEventMaskKeyUp | NSEventMaskFlagsChanged

        def handler(event: Any) -> None:
            try:
                self._handle(event)
            except Exception:
                pass

        self._monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, handler
        )
        if self._monitor is None:
            raise RuntimeError(
                "Kon geen globale toetsenmonitor starten. "
                "Zet Toegankelijkheid aan voor Terminal (of de .app) in "
                "Systeeminstellingen → Privacy en beveiliging."
            )

    def stop(self) -> None:
        if self._monitor is None:
            return
        try:
            from AppKit import NSEvent  # type: ignore[import-not-found]

            NSEvent.removeMonitor_(self._monitor)
        except Exception:
            pass
        self._monitor = None
        self._mod_down.clear()

    def _handle(self, event: Any) -> None:
        from AppKit import (  # type: ignore[import-not-found]
            NSEventTypeFlagsChanged,
            NSEventTypeKeyDown,
            NSEventTypeKeyUp,
        )

        etype = event.type()
        keycode = int(event.keyCode())

        if etype == NSEventTypeFlagsChanged:
            token = _MOD_KEYCODES.get(keycode)
            if token is None:
                return
            # FlagsChanged: bepaal of de modifier nu aan of uit staat.
            flags = int(event.modifierFlags())
            flag_bits = {
                "cmd": 1 << 20,  # NSEventModifierFlagCommand
                "shift": 1 << 17,
                "alt": 1 << 19,
                "ctrl": 1 << 18,
            }
            is_down = bool(flags & flag_bits[token])
            was_down = token in self._mod_down
            if is_down and not was_down:
                self._mod_down.add(token)
                self._on_press(MacKey(token))
            elif not is_down and was_down:
                self._mod_down.discard(token)
                self._on_release(MacKey(token))
            return

        token = _token_for_keycode(keycode)
        if token is None:
            return
        key = MacKey(token)
        if etype == NSEventTypeKeyDown:
            if event.isARepeat():
                return
            self._on_press(key)
        elif etype == NSEventTypeKeyUp:
            self._on_release(key)
