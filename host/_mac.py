"""
macOS-adapter voor de platform-seam (`host`).

Tegenhanger van `_win.py`. `paste()` en `app_dir()` zijn volledig en volgen de
macOS-conventies. Het automatisch meestarten gebruikt een LaunchAgent-plist onder
`~/Library/LaunchAgents/`.

LaunchAgent-plist onder `~/Library/LaunchAgents/`. Op een echte Mac nog
handmatig verifiëren (paste + login-item); unit-tests dekken app_dir/plist.
"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

from . import APP_NAME

# Reverse-DNS label voor de LaunchAgent.
_AGENT_LABEL = "nl.wulf.praatmaar"


class MacHost:
    """De `Host`-implementatie voor macOS."""

    def paste(self) -> None:
        # Quartz CGEvents i.p.v. pyautogui/pynput: die raken TSM en crashen
        # op macOS 26+ vanaf een niet-main-thread.
        from mac_input import paste_command_v

        paste_command_v()

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
            try:
                other = lock_path.read_text(encoding="utf-8").strip()
            except OSError:
                other = "?"
            print(
                f"Er draait al een praatMaar-proces (PID {other or '?'}). "
                "Sluit die eerst via het menubalk-icoon → Afsluiten, "
                "anders zie je twee microfoon-iconen."
            )
            handle.close()
            return False

        # Bestand open (en dus de flock) houden voor de procesduur; het OS geeft de
        # grendel vrij zodra dit proces stopt (ook bij een crash).
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._lock = handle
        return True

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_AGENT_LABEL}.plist"

    def is_autostart_enabled(self) -> bool:
        return self._plist_path().exists()

    def set_autostart(self, enabled: bool) -> None:
        """
        Schrijft of verwijdert de LaunchAgent-plist.

        Geen `launchctl bootstrap` bij aanzetten: dat zou de app meteen opnieuw
        starten. `RunAtLoad` geldt bij de volgende login.
        """

        path = self._plist_path()

        if not enabled:
            path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        plist = {
            "Label": _AGENT_LABEL,
            "ProgramArguments": self._program_arguments(),
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
        with path.open("wb") as handle:
            plistlib.dump(plist, handle)

    def _program_arguments(self) -> list[str]:
        """De opdracht die macOS bij het inloggen moet uitvoeren."""

        if getattr(sys, "frozen", False):
            # App-bundle: sys.executable is .../Foo.app/Contents/MacOS/Foo.
            return [sys.executable]

        # Vanuit broncode: de huidige Python + het hoofdscript, één map boven
        # deze adapter.
        script = Path(__file__).resolve().parent.parent / "dictation.py"
        return [sys.executable, str(script)]
