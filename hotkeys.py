"""
Gedeelde sneltoets-logica voor praatMaar.

Zet pynput-toetsen om naar stabiele 'tokens' (strings) en weer terug naar een
leesbaar label. Zowel de globale listener (dictation.py) als het opnemen van een
nieuwe sneltoets in het instellingen-dialoog (settings.py) gebruiken dit, zodat
een opgeslagen combinatie exact overeenkomt met wat de listener herkent.

pynput wordt niet bij import geladen (dat zou het laadscherm vertragen): roep
eerst `init(keyboard)` aan zodra pynput beschikbaar is.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any

_keyboard: Any = None

# Worden in init() gevuld zodra pynput bekend is.
CTRL_KEYS: set = set()
SHIFT_KEYS: set = set()
ALT_KEYS: set = set()
CMD_KEYS: set = set()

MODIFIER_TOKENS = ("ctrl", "shift", "alt", "cmd")

# De standaard-sneltoets als de gebruiker (nog) niets heeft ingesteld.
DEFAULT_HOTKEY = ["ctrl", "shift", "alt", "space"]

# Windows/pynput levert speciale toetsen soms als Key.* en soms als KeyCode(vk=…).
# Zonder mapping blijft bijv. Esc als "esc" hangen terwijl release "vk27" is —
# dan triggert alleen Shift nog de hotkey Shift+Esc.
_VK_TO_TOKEN = {
    0x08: "backspace",
    0x09: "tab",
    0x0D: "enter",
    0x1B: "esc",
    0x20: "space",
    0x21: "page_up",
    0x22: "page_down",
    0x23: "end",
    0x24: "home",
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x2D: "insert",
    0x2E: "delete",
}
for _i in range(1, 25):
    _VK_TO_TOKEN[0x6F + _i] = f"f{_i}"  # VK_F1=0x70 … VK_F24

# Token -> virtuele toetscode, voor het opvragen van de échte toetsstatus bij het
# OS. Nodig omdat press/release-boekhouding alleen klopt als beide events dezelfde
# token opleveren; bij Shift+Esc gebeurde dat niet (zie #44 en
# tests/test_hotkey_physical_state.py).
_MODIFIER_VKS = {
    "shift": 0x10,  # VK_SHIFT
    "ctrl": 0x11,  # VK_CONTROL
    "alt": 0x12,  # VK_MENU
    "cmd": 0x5B,  # VK_LWIN (rechter Win wordt apart gecheckt)
}


def token_to_vk(token: str) -> int | None:
    """Virtuele toetscode voor een hotkey-token, of None als die onbekend is."""

    if not token:
        return None
    key = token.lower()
    if key in _MODIFIER_VKS:
        return _MODIFIER_VKS[key]
    if len(key) == 1 and (key.isdigit() or ("a" <= key <= "z")):
        return ord(key.upper())
    for vk, mapped in _VK_TO_TOKEN.items():
        if mapped == key:
            return vk
    return None


# Nette weergave per token (Windows-default); macOS overschrijft via _display_names().
_DISPLAY_NAMES_WIN = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "space": None,  # via i18n key.space
    "enter": "Enter",
    "tab": "Tab",
    "esc": "Esc",
    "cmd": "Win",
    "cmd_l": "Win",
    "cmd_r": "Win",
    "backspace": "Backspace",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "page_up": "PageUp",
    "page_down": "PageDown",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "section": "<>",
}

_DISPLAY_NAMES_MAC = {
    **_DISPLAY_NAMES_WIN,
    "ctrl": "Control",
    "alt": "Option",
    # Win-toets op een PC-board = Command op macOS.
    "cmd": "Command (Win)",
    "cmd_l": "Command (Win)",
    "cmd_r": "Command (Win)",
}


def _display_names() -> dict[str, str]:
    if sys.platform == "darwin":
        return _DISPLAY_NAMES_MAC
    return _DISPLAY_NAMES_WIN


def init(keyboard_module: Any) -> None:
    """Koppelt het (lazy geladen) pynput.keyboard en bouwt de modifier-sets."""

    global _keyboard, CTRL_KEYS, SHIFT_KEYS, ALT_KEYS, CMD_KEYS

    _keyboard = keyboard_module
    key = keyboard_module.Key
    CTRL_KEYS = {key.ctrl, key.ctrl_l, key.ctrl_r}
    SHIFT_KEYS = {key.shift, key.shift_l, key.shift_r}
    ALT_KEYS = {key.alt, key.alt_l, key.alt_r}
    CMD_KEYS = set()
    for name in ("cmd", "cmd_l", "cmd_r", "command", "command_l", "command_r"):
        if hasattr(key, name):
            CMD_KEYS.add(getattr(key, name))


def key_to_token(key: Any) -> str | None:
    """
    Zet een pynput-toets (of macOS `MacKey`) om naar een stabiel token.

    Modifiers worden samengevouwen tot 'ctrl'/'shift'/'alt'/'cmd'. Letters en
    cijfers gaan via hun virtuele toetscode, zodat het token hetzelfde blijft
    ongeacht of Shift het teken verandert.
    """

    # host._mac_hotkeys.MacKey (Quartz/NSEvent) — geen pynput nodig.
    token = getattr(key, "praatmaar_token", None)
    if isinstance(token, str) and token:
        return token

    if _keyboard is None:
        return None

    if key in CTRL_KEYS:
        return "ctrl"
    if key in SHIFT_KEYS:
        return "shift"
    if key in ALT_KEYS:
        return "alt"
    if key in CMD_KEYS:
        return "cmd"

    if isinstance(key, _keyboard.Key):
        name = key.name
        if name in ("cmd", "cmd_l", "cmd_r", "command", "command_l", "command_r"):
            return "cmd"
        return name

    if isinstance(key, _keyboard.KeyCode):
        vk = key.vk
        if vk is not None and (48 <= vk <= 57 or 65 <= vk <= 90):
            return chr(vk).lower()
        if vk is not None and vk in _VK_TO_TOKEN:
            return _VK_TO_TOKEN[vk]
        if key.char:
            return key.char.lower()
        if vk is not None:
            return f"vk{vk}"

    return None


def qt_key_to_token(key: Any, text: str = "") -> str | None:
    """Convert a Qt key code and optional event text to a persistent hotkey token."""
    from PySide6.QtCore import Qt

    special_keys = {
        Qt.Key.Key_Control: "ctrl",
        Qt.Key.Key_Shift: "shift",
        Qt.Key.Key_Alt: "alt",
        Qt.Key.Key_Meta: "cmd",
        Qt.Key.Key_Space: "space",
        Qt.Key.Key_Return: "enter",
        Qt.Key.Key_Enter: "num_enter",
        Qt.Key.Key_Tab: "tab",
        Qt.Key.Key_Escape: "esc",
        Qt.Key.Key_Backspace: "backspace",
        Qt.Key.Key_Delete: "delete",
        Qt.Key.Key_Insert: "insert",
        Qt.Key.Key_Home: "home",
        Qt.Key.Key_End: "end",
        Qt.Key.Key_PageUp: "page_up",
        Qt.Key.Key_PageDown: "page_down",
        Qt.Key.Key_Left: "left",
        Qt.Key.Key_Right: "right",
        Qt.Key.Key_Up: "up",
        Qt.Key.Key_Down: "down",
        Qt.Key.Key_BracketLeft: "[",
        Qt.Key.Key_BracketRight: "]",
        Qt.Key.Key_Backslash: "\\",
        Qt.Key.Key_Semicolon: ";",
        Qt.Key.Key_Apostrophe: "'",
        Qt.Key.Key_Comma: ",",
        Qt.Key.Key_Period: ".",
        Qt.Key.Key_Slash: "/",
        Qt.Key.Key_Minus: "-",
        Qt.Key.Key_Equal: "=",
        Qt.Key.Key_QuoteLeft: "`",
    }
    if key in special_keys:
        return special_keys[key]
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(int(key) - int(Qt.Key.Key_A) + ord("a"))
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(int(key) - int(Qt.Key.Key_0) + ord("0"))
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35:
        return f"f{int(key) - int(Qt.Key.Key_F1) + 1}"
    if len(text) == 1 and not text.isspace():
        return text.lower()
    return None


def normalize(tokens: Iterable[str]) -> list[str]:
    """Ontdubbelt en sorteert (modifiers eerst) voor een stabiele opslag/weergave."""

    unique = set(tokens)
    mods = [token for token in MODIFIER_TOKENS if token in unique]
    rest = sorted(token for token in unique if token not in MODIFIER_TOKENS)
    return mods + rest


def format_hotkey(tokens: Iterable[str]) -> str:
    """Maakt een leesbaar label, bijv. 'Ctrl + Shift + Alt + Spatie'."""

    import i18n

    parts = normalize(tokens)
    if not parts:
        return "(geen)"

    names = _display_names()
    labels: list[str] = []
    for token in parts:
        if token == "space":
            labels.append(i18n.t("key.space"))
        elif token in names and names[token] is not None:
            labels.append(names[token])
        elif len(token) == 1:
            labels.append(token.upper())
        elif token.startswith("f") and token[1:].isdigit():
            labels.append(token.upper())
        else:
            labels.append(token.capitalize())

    return " + ".join(labels)
