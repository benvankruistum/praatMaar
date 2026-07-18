"""
macOS-toetsenbord via AppKit NSEvent (main thread) — geen pynput.

Op macOS 26+ crasht pynput's Listener: die raakt TSM/HIToolbox vanaf een
achtergrondthread (`dispatch_assert_queue` / SIGTRAP). NSEvent-monitors lopen
op de Cocoa-mainloop (dezelfde als pystray) en vermijden die API.

Paste gebeurt met Quartz CGEvents (⌘V via keycode), niet via pyautogui/pynput.

Windows-/ISO-toetsenborden: modifiers worden uit ``modifierFlags`` gelezen
(niet alleen uit bekende keycodes), en onbekende toetsen vallen terug op
``charactersIgnoringModifiers`` of ``kc<n>``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# ANSI/US + veelgebruikte extra keycodes → tokens (fysieke toets).
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
    0x0A: "section",  # ISO-toets links van Z / bij Shift (vaak <> op PC)
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
    0x72: "insert",
    0x73: "home",
    0x77: "end",
    0x74: "page_up",
    0x79: "page_down",
    0x7B: "left",
    0x7C: "right",
    0x7D: "down",
    0x7E: "up",
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
    # Numpad
    0x52: "num0",
    0x53: "num1",
    0x54: "num2",
    0x55: "num3",
    0x56: "num4",
    0x57: "num5",
    0x58: "num6",
    0x59: "num7",
    0x5B: "num8",
    0x5C: "num9",
    0x4C: "num_enter",
    0x45: "num_add",
    0x4E: "num_sub",
    0x43: "num_mul",
    0x4B: "num_div",
    0x41: "num_dec",
    0x47: "num_clear",
}

# Modifier keycodes (FlagsChanged) — aanvullend; primaire bron is modifierFlags.
_MOD_KEYCODES: dict[int, str] = {
    0x37: "cmd",  # left command / Windows-toets
    0x36: "cmd",  # right command
    0x38: "shift",
    0x3C: "shift",
    0x3A: "alt",  # option / Alt
    0x3D: "alt",
    0x3B: "ctrl",
    0x3E: "ctrl",
}

_MODIFIER_FLAG_BITS: dict[str, int] = {
    "cmd": 1 << 20,  # NSEventModifierFlagCommand (Win-toets op PC-boards)
    "shift": 1 << 17,
    "alt": 1 << 19,  # Option / Alt / AltGr (deels)
    "ctrl": 1 << 18,
}

# NSEvent function-key Unicode (charactersIgnoringModifiers).
_FUNCTION_CHAR_TOKENS: dict[int, str] = {
    0xF700: "up",
    0xF701: "down",
    0xF702: "left",
    0xF703: "right",
    0xF704: "f1",
    0xF705: "f2",
    0xF706: "f3",
    0xF707: "f4",
    0xF708: "f5",
    0xF709: "f6",
    0xF70A: "f7",
    0xF70B: "f8",
    0xF70C: "f9",
    0xF70D: "f10",
    0xF70E: "f11",
    0xF70F: "f12",
    0xF727: "insert",
    0xF728: "delete",
    0xF729: "home",
    0xF72B: "end",
    0xF72C: "page_up",
    0xF72D: "page_down",
}

_KEY_V = 0x09
_MODIFIER_TOKENS = frozenset(_MODIFIER_FLAG_BITS)


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


def _token_from_characters(chars: str | None) -> str | None:
    if not chars:
        return None
    ch = chars[0]
    code = ord(ch)
    if code in _FUNCTION_CHAR_TOKENS:
        return _FUNCTION_CHAR_TOKENS[code]
    if ch == " ":
        return "space"
    if ch in ("\r", "\n"):
        return "enter"
    if ch == "\t":
        return "tab"
    if ch == "\x1b":
        return "esc"
    if ch == "\x08" or ch == "\x7f":
        return "backspace"
    # Printbare ASCII (letters/cijfers/leestekens op PC- en ISO-layouts).
    if 33 <= code <= 126:
        return ch.lower()
    return None


def token_for_nsevent(event: Any) -> str | None:
    """
    Zet een NSEvent om naar een hotkey-token.

    Volgorde: bekende keycode → charactersIgnoringModifiers → kc<keycode>.
    Modifiers zelf worden via modifierFlags gesynchroniseerd, niet hier.
    """

    keycode = int(event.keyCode())
    if keycode in _MOD_KEYCODES:
        return _MOD_KEYCODES[keycode]

    mapped = _KEYCODE_TOKENS.get(keycode)
    if mapped is not None:
        return mapped

    try:
        chars = event.charactersIgnoringModifiers()
    except Exception:
        chars = None
    from_chars = _token_from_characters(chars if isinstance(chars, str) else None)
    if from_chars is not None:
        return from_chars

    # Laatste redmiddel: fysieke toets blijft matchbaar bij dicteren.
    return f"kc{keycode}"


class QuartzKeyListener:
    """
    Globale toetsenmonitor op de Cocoa-mainloop.

    API-compatibiliteit met pynput.Listener: `start()` / `stop()`, callbacks
    `on_press` / `on_release` krijgen een `MacKey`.

    Modifiers komen uit ``modifierFlags`` (betrouwbaar op Windows-toetsenborden
    waar Win=Command en Alt=Option); gewone toetsen via keycode + fallback.
    """

    def __init__(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None],
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._global_monitor: Any = None
        self._local_monitor: Any = None
        self._mod_down: set[str] = set()

    def start(self) -> None:
        if self._global_monitor is not None or self._local_monitor is not None:
            return

        from AppKit import (  # type: ignore[import-not-found]
            NSEvent,
            NSEventMaskFlagsChanged,
            NSEventMaskKeyDown,
            NSEventMaskKeyUp,
        )

        mask = NSEventMaskKeyDown | NSEventMaskKeyUp | NSEventMaskFlagsChanged

        def global_handler(event: Any) -> None:
            try:
                self._handle(event)
            except Exception:
                pass

        def local_handler(event: Any) -> Any:
            try:
                self._handle(event)
            except Exception:
                pass
            return event

        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, global_handler
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            mask, local_handler
        )
        if self._global_monitor is None and self._local_monitor is None:
            raise RuntimeError(
                "Kon geen toetsenmonitor starten. "
                "Zet Toegankelijkheid aan voor Terminal (of de .app) in "
                "Systeeminstellingen → Privacy en beveiliging."
            )

    def stop(self) -> None:
        if self._global_monitor is None and self._local_monitor is None:
            return
        try:
            from AppKit import NSEvent  # type: ignore[import-not-found]

            if self._global_monitor is not None:
                NSEvent.removeMonitor_(self._global_monitor)
            if self._local_monitor is not None:
                NSEvent.removeMonitor_(self._local_monitor)
        except Exception:
            pass
        self._global_monitor = None
        self._local_monitor = None
        self._mod_down.clear()

    def _sync_modifiers(self, flags: int) -> None:
        for token, bit in _MODIFIER_FLAG_BITS.items():
            is_down = bool(flags & bit)
            was_down = token in self._mod_down
            if is_down and not was_down:
                self._mod_down.add(token)
                self._on_press(MacKey(token))
            elif not is_down and was_down:
                self._mod_down.discard(token)
                self._on_release(MacKey(token))

    def _handle(self, event: Any) -> None:
        from AppKit import (  # type: ignore[import-not-found]
            NSEventTypeFlagsChanged,
            NSEventTypeKeyDown,
            NSEventTypeKeyUp,
        )

        etype = event.type()
        flags = int(event.modifierFlags())
        # Altijd uit flags: Win-toets=Command, Alt=Option, ook als keycode afwijkt.
        self._sync_modifiers(flags)

        if etype == NSEventTypeFlagsChanged:
            return

        token = token_for_nsevent(event)
        if token is None or token in _MODIFIER_TOKENS:
            return

        key = MacKey(token)
        if etype == NSEventTypeKeyDown:
            if event.isARepeat():
                return
            self._on_press(key)
        elif etype == NSEventTypeKeyUp:
            self._on_release(key)
