"""Linux adapter for the platform seam.

``paste()`` is intentionally best-effort.  X11 and Wayland do not expose one
portable, permission-free API for sending a paste shortcut, so it tries
``xdotool`` first and then ``ydotool`` when either is installed.  On systems
without either utility, the text remains on the clipboard but is not pasted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import APP_NAME


class LinuxHost:
    """The Linux implementation of :class:`host.Host`."""

    def paste(self) -> None:
        """Best-effort Ctrl+V via an installed desktop input utility."""
        commands = (
            ("xdotool", "key", "--clearmodifiers", "ctrl+v"),
            ("ydotool", "key", "29:1", "47:1", "47:0", "29:0"),
        )
        for command in commands:
            if shutil.which(command[0]) is None:
                continue
            try:
                result = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                return

    def app_dir(self) -> Path:
        base = os.environ.get("XDG_DATA_HOME")
        path = Path(base) if base else Path.home() / ".local" / "share"
        path = path / APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def acquire_single_instance(self) -> bool:
        """Acquire and retain a non-blocking advisory lock for this process."""
        if getattr(self, "_lock", None) is not None:
            return True

        import fcntl

        lock_path = self.app_dir() / "singleton.lock"
        handle = lock_path.open("w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False

        handle.write(str(os.getpid()))
        handle.flush()
        self._lock = handle
        return True

    def is_autostart_enabled(self) -> bool:
        return self._desktop_path().exists()

    def set_autostart(self, enabled: bool) -> None:
        path = self._desktop_path()
        if not enabled:
            path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                (
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=praatMaar",
                    f"Exec={self._launch_command()}",
                    "X-GNOME-Autostart-enabled=true",
                    "",
                )
            ),
            encoding="utf-8",
        )

    def _desktop_path(self) -> Path:
        base = os.environ.get("XDG_CONFIG_HOME")
        config_home = Path(base) if base else Path.home() / ".config"
        return config_home / "autostart" / f"{APP_NAME}.desktop"

    def _launch_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        script = Path(__file__).resolve().parent.parent / "dictation.py"
        return f'"{sys.executable}" "{script}"'
