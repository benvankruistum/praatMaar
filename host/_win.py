"""
Windows-adapter voor de platform-seam (`host`).

Absorbeert wat voorheen in `autostart.py` en verspreid door de app stond: de
`winreg`-Run-sleutel, de launch-opdracht (gebouwde .exe of pythonw + script), de
plak-toets en de `%APPDATA%`-datamap.

Zware libraries (pyautogui) worden pas in de methode geïmporteerd; de constructie
moet licht blijven omdat `host` al bij het opstarten wordt geïmporteerd.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME
from ._launch import dictation_script_path

# Per-gebruiker 'Run'-sleutel — geen adminrechten nodig.
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = APP_NAME

# Naam van het mutex-kernelobject voor de single-instance-grendel. Zonder
# namespace-prefix zit dit in de sessie-lokale namespace: per ingelogde gebruiker
# apart, precies wat we willen voor een desktop-app.
_MUTEX_NAME = "praatMaar-singleton"
_ERROR_ALREADY_EXISTS = 183


class WinHost:
    """De `Host`-implementatie voor Windows."""

    def paste(self) -> None:
        import pyautogui

        pyautogui.hotkey("ctrl", "v")

    def app_dir(self) -> Path:
        # resolve(): onder Microsoft Store-Python is %APPDATA% gevirtualiseerd;
        # Verkenner (os.startfile) ziet alleen het echte pad (LocalCache/...).
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = Path(base) / APP_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def acquire_single_instance(self) -> bool:
        import ctypes
        from ctypes import wintypes

        # use_last_error=True + get_last_error(): ctypes zelf kan LastError
        # tussentijds overschrijven, waardoor windll.kernel32.GetLastError()
        # onbetrouwbaar is (tweede instantie zag dan 0 i.p.v. ALREADY_EXISTS).
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPCVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]

        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            # Kon geen mutex maken: fail-open — liever laten starten dan de enige
            # instantie ten onrechte blokkeren.
            return True

        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            return False

        # Handle levend houden voor de procesduur; het OS geeft de mutex vrij zodra
        # dit proces stopt (ook bij een crash).
        self._mutex = handle
        return True

    def keys_physically_down(self, tokens: set[str]) -> set[str] | None:
        """Vraagt Windows welke tokens nu echt ingedrukt zijn (GetAsyncKeyState).

        De press/release-boekhouding van de listener kan uit de pas lopen wanneer
        een release een andere token oplevert dan de press — bij Shift+Esc bleef
        "esc" dan hangen en vuurde Shift alleen de sneltoets. Deze check is de
        waarheid van het OS; onbekende tokens laten we buiten beschouwing.
        """

        import ctypes

        import hotkeys

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
        except OSError:
            return None

        # Hoogste bit gezet = toets is op dit moment ingedrukt.
        down_mask = 0x8000
        down: set[str] = set()
        for token in tokens:
            vk = hotkeys.token_to_vk(token)
            if vk is None:
                # Niet te controleren: neem het token op gezag van de listener aan,
                # anders zou een exotische toets de sneltoets blokkeren.
                down.add(token)
                continue
            state = user32.GetAsyncKeyState(vk)
            pressed = bool(state & down_mask)
            if not pressed and token == "cmd":
                # Rechter Windows-toets heeft een eigen vk.
                pressed = bool(user32.GetAsyncKeyState(0x5C) & down_mask)
            if pressed:
                down.add(token)
        return down

    def is_autostart_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
                return bool(value)
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def set_autostart(self, enabled: bool) -> None:
        import winreg

        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, self._launch_command())
            return

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _VALUE_NAME)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _launch_command(self) -> str:
        """De opdracht die Windows bij het inloggen moet uitvoeren."""

        if getattr(sys, "frozen", False):
            # PyInstaller-bundle: sys.executable is de app-exe zelf.
            return f'"{sys.executable}"'

        # Vanuit broncode: pythonw.exe (zonder console) + het hoofdscript, dat
        # één map boven deze adapter staat.
        script = dictation_script_path()
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        executable = pythonw if pythonw.exists() else Path(sys.executable)
        return f'"{executable}" "{script}"'
