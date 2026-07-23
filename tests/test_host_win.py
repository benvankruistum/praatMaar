"""Tests voor host._win.app_dir (canonieke resolve na mkdir)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from host import APP_NAME
from host._win import WinHost

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_app_dir_mkdir_and_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    host = WinHost()
    result = host.app_dir()
    expected = (appdata / APP_NAME).resolve()
    assert result == expected
    assert result.is_dir()
    assert result.is_absolute()
