"""
Platform-seam voor praatMaar.

Eén plek voor alles wat per besturingssysteem verschilt: de plak-toets, het
automatisch meestarten en de map voor gebruikersdata. De rest van de app praat
alleen met deze `host`-module en raakt nooit rechtstreeks `winreg`, `ctypes` of
een OS-specifieke plak-toets aan.

Vorm: een `Host`-Protocol met per besturingssysteem één instantie, gekozen op
`sys.platform`. Zo is de seam een echt testoppervlak — een `FakeHost` is
injecteerbaar waar code een `Host` verwacht (zie de opnamesessie).

De module heet bewust `host` en niet `platform`: dat laatste zou de gelijknamige
stdlib-module schaduwen.

Gebruik::

    import host
    host.paste()
    directory = host.app_dir()

De adapters (`_win`, `_mac`) importeren hun zware libraries (pyautogui, winreg)
pas in de methode-aanroep, niet bij constructie: `default = _select()` draait al
bij het importeren van deze module — ruim vóór het laadscherm — en moet licht
blijven.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

# Naam van de app-map onder de OS-datamap; gedeeld door beide adapters.
APP_NAME = "praatMaar"


class Host(Protocol):
    """De OS-afhankelijke operaties die de app nodig heeft."""

    def paste(self) -> None:
        """Stuurt de plak-toetscombinatie (Ctrl+V op Windows, Cmd+V op macOS)."""
        ...

    def set_autostart(self, enabled: bool) -> None:
        """Zet automatisch meestarten met het inloggen aan of uit."""
        ...

    def is_autostart_enabled(self) -> bool:
        """True als de app automatisch meestart."""
        ...

    def app_dir(self) -> Path:
        """De OS-conforme map voor gebruikersdata (config, transcripts, herstel)."""
        ...

    def acquire_single_instance(self) -> bool:
        """
        Claimt de single-instance-grendel. True als dit de enige (eerste) instantie
        is; False als de app al draait. De grendel blijft de procesduur vast en
        wordt door het OS vrijgegeven zodra het proces stopt (ook bij een crash).
        """
        ...


def _select() -> Host:
    """Kiest de adapter voor het huidige besturingssysteem."""

    if sys.platform == "win32":
        from ._win import WinHost

        return WinHost()

    if sys.platform == "darwin":
        from ._mac import MacHost

        return MacHost()

    raise RuntimeError(f"Niet-ondersteund platform: {sys.platform!r}")


# De gekozen instantie voor dit besturingssysteem. Code die wil substitueren
# (tests) accepteert zelf een `Host`; vrije consumenten gebruiken deze default
# via de gemaksfuncties hieronder.
default: Host = _select()


def paste() -> None:
    default.paste()


def set_autostart(enabled: bool) -> None:
    default.set_autostart(enabled)


def is_autostart_enabled() -> bool:
    return default.is_autostart_enabled()


def app_dir() -> Path:
    return default.app_dir()


def acquire_single_instance() -> bool:
    return default.acquire_single_instance()
