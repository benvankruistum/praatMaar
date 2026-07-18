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

from typing import Any, Iterable

_keyboard: Any = None

# Worden in init() gevuld zodra pynput bekend is.
CTRL_KEYS: set = set()
SHIFT_KEYS: set = set()
ALT_KEYS: set = set()

MODIFIER_TOKENS = ("ctrl", "shift", "alt")

# De standaard-sneltoets als de gebruiker (nog) niets heeft ingesteld.
DEFAULT_HOTKEY = ["ctrl", "shift", "alt", "space"]

# Nette weergave per token; overige tokens worden generiek opgemaakt.
_DISPLAY_NAMES = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "space": "Spatie",
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
}


def init(keyboard_module: Any) -> None:
    """Koppelt het (lazy geladen) pynput.keyboard en bouwt de modifier-sets."""

    global _keyboard, CTRL_KEYS, SHIFT_KEYS, ALT_KEYS

    _keyboard = keyboard_module
    key = keyboard_module.Key
    CTRL_KEYS = {key.ctrl, key.ctrl_l, key.ctrl_r}
    SHIFT_KEYS = {key.shift, key.shift_l, key.shift_r}
    ALT_KEYS = {key.alt, key.alt_l, key.alt_r}


def key_to_token(key: Any) -> str | None:
    """
    Zet een pynput-toets om naar een stabiel token.

    Modifiers worden samengevouwen tot 'ctrl'/'shift'/'alt'. Letters en cijfers
    gaan via hun virtuele toetscode, zodat het token hetzelfde blijft ongeacht of
    Shift het teken verandert (Shift+r levert anders 'R', Shift+1 een '!').
    """

    if _keyboard is None:
        return None

    if key in CTRL_KEYS:
        return "ctrl"
    if key in SHIFT_KEYS:
        return "shift"
    if key in ALT_KEYS:
        return "alt"

    if isinstance(key, _keyboard.Key):
        return key.name  # bijv. space, f9, esc, home

    if isinstance(key, _keyboard.KeyCode):
        vk = key.vk
        if vk is not None and (48 <= vk <= 57 or 65 <= vk <= 90):
            return chr(vk).lower()
        if key.char:
            return key.char.lower()
        if vk is not None:
            return f"vk{vk}"

    return None


def normalize(tokens: Iterable[str]) -> list[str]:
    """Ontdubbelt en sorteert (modifiers eerst) voor een stabiele opslag/weergave."""

    unique = set(tokens)
    mods = [token for token in MODIFIER_TOKENS if token in unique]
    rest = sorted(token for token in unique if token not in MODIFIER_TOKENS)
    return mods + rest


def format_hotkey(tokens: Iterable[str]) -> str:
    """Maakt een leesbaar label, bijv. 'Ctrl + Shift + Alt + Spatie'."""

    parts = normalize(tokens)
    if not parts:
        return "(geen)"

    labels: list[str] = []
    for token in parts:
        if token in _DISPLAY_NAMES:
            labels.append(_DISPLAY_NAMES[token])
        elif len(token) == 1:
            labels.append(token.upper())
        elif token.startswith("f") and token[1:].isdigit():
            labels.append(token.upper())  # functietoetsen: F1..F12
        else:
            labels.append(token.capitalize())

    return " + ".join(labels)
