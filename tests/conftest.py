"""Suite-brede isolatie: nooit de echte gebruikersdata of proces-globale taal raken.

Twee lekken die deze conftest dicht:

1. ``import dictation`` (al bij collectie) las de echte ``%APPDATA%\\praatMaar\\
   config.json`` en tests met achterlopende daemon-threads schreven — en
   pruneden! — de echte ``transcripts\\``-map van de gebruiker. Alle config-/
   recovery-paden wijzen hier naar een sessie-tijdelijke map.
2. Tests die ``i18n.set_ui_language`` aanroepen lieten de proces-globale taal
   achter voor alfabetisch latere tests; een autouse-fixture herstelt "nl".
"""

from __future__ import annotations

import os

# Qt headless vóór elke PySide6-import (zelfde als CI op Windows; voorkomt macOS
# abort in _RegisterApplication bij pytest vanuit een terminal/Cursor-sessie).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
from pathlib import Path

import pytest

import config as _config
import recovery as _recovery

# Module-level (vóór het importeren van testmodules en dus vóór ``import
# dictation``): standaard-datamap van de suite is een wegwerp-map.
_SUITE_DATA_DIR = Path(tempfile.mkdtemp(prefix="praatMaar-tests-"))


def _suite_config_dir() -> Path:
    return _SUITE_DATA_DIR


_config.config_dir = _suite_config_dir
_recovery.config_dir = _suite_config_dir


@pytest.fixture(autouse=True)
def _reset_ui_language():
    import i18n

    i18n.set_ui_language("nl")
    yield
    i18n.set_ui_language("nl")
