"""
Windows-app-identiteit voor praatMaar.

Zet vroeg in het proces een AppUserModelID, zodat Windows de app niet als
generieke Python-sessie groepeert. De zichtbare naam in
Instellingen → Taakbalk → pictogrammen komt van de **FileDescription** van
het .exe-bestand — die staat in `version_info.txt` voor PyInstaller-builds.
Draaien via `pythonw.exe` blijft in die lijst als "Python" staan; gebruik
daarvoor `praatMaar.exe` (Setup of `dist\\`).
"""

from __future__ import annotations

import sys


APP_USER_MODEL_ID = "benvankruistum.praatMaar"


def apply_windows_app_identity() -> None:
    """No-op buiten Windows; faalt stil als de API ontbreekt."""

    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        pass
