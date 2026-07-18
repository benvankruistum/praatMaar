"""
macOS-adapter voor de platform-seam (`host`).

Tegenhanger van `_win.py`. `paste()` en `app_dir()` zijn volledig en volgen de
macOS-conventies. Het automatisch meestarten gebruikt een LaunchAgent-plist onder
`~/Library/LaunchAgents/`.

LET OP — deze adapter is nog NIET op een Mac getest (de seam is op Windows
gebouwd). `paste()`/`app_dir()` zijn triviaal en veilig; de LaunchAgent-logica is
plausibel maar moet op de Mac geverifieerd worden. Zie `docs/HANDOFF-mac-port.md`.
"""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

from . import APP_NAME

# Reverse-DNS label voor de LaunchAgent.
_AGENT_LABEL = "nl.wulf.praatmaar"


class MacHost:
    """De `Host`-implementatie voor macOS."""

    def paste(self) -> None:
        import pyautogui

        # pyautogui gebruikt "command" voor de Cmd-toets op macOS.
        pyautogui.hotkey("command", "v")

    def app_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / APP_NAME

    def acquire_single_instance(self) -> bool:
        import fcntl

        lock_path = self.app_dir() / "singleton.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        handle = lock_path.open("w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Een andere instantie houdt de grendel al vast.
            handle.close()
            return False

        # Bestand open (en dus de flock) houden voor de procesduur; het OS geeft de
        # grendel vrij zodra dit proces stopt (ook bij een crash).
        self._lock = handle
        return True

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_AGENT_LABEL}.plist"

    def is_autostart_enabled(self) -> bool:
        return self._plist_path().exists()

    def set_autostart(self, enabled: bool) -> None:
        path = self._plist_path()

        if not enabled:
            path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        plist = {
            "Label": _AGENT_LABEL,
            "ProgramArguments": self._program_arguments(),
            "RunAtLoad": True,
        }
        with path.open("wb") as handle:
            plistlib.dump(plist, handle)

    def _program_arguments(self) -> list[str]:
        """De opdracht die macOS bij het inloggen moet uitvoeren."""

        if getattr(sys, "frozen", False):
            # App-bundle: sys.executable is de gebundelde binary zelf.
            return [sys.executable]

        # Vanuit broncode: de huidige Python + het hoofdscript, één map boven
        # deze adapter.
        script = Path(__file__).resolve().parent.parent / "dictation.py"
        return [sys.executable, str(script)]
