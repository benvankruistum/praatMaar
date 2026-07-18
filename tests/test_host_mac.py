"""Tests voor host._mac (geen echte Mac nodig voor app_dir/plist)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest

from host._mac import _AGENT_LABEL, MacHost


@pytest.fixture()
def mac_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda *args, **kwargs: tmp_path)
    return tmp_path


def test_app_dir_under_application_support(mac_home: Path) -> None:
    host = MacHost()
    assert host.app_dir() == mac_home / "Library" / "Application Support" / "praatMaar"


def test_autostart_writes_and_removes_plist(mac_home: Path) -> None:
    host = MacHost()
    assert host.is_autostart_enabled() is False

    host.set_autostart(True)
    plist_path = mac_home / "Library" / "LaunchAgents" / f"{_AGENT_LABEL}.plist"
    assert plist_path.is_file()
    assert host.is_autostart_enabled() is True

    with plist_path.open("rb") as handle:
        data = plistlib.load(handle)
    assert data["Label"] == _AGENT_LABEL
    assert data["RunAtLoad"] is True
    assert isinstance(data["ProgramArguments"], list)
    assert len(data["ProgramArguments"]) >= 1

    host.set_autostart(False)
    assert not plist_path.exists()
    assert host.is_autostart_enabled() is False


def test_program_arguments_include_dictation_script(mac_home: Path) -> None:
    host = MacHost()
    args = host._program_arguments()
    assert args[0]
    assert args[-1].endswith("dictation.py")


def test_single_instance_writes_pid(mac_home: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("fcntl.flock bestaat niet op Windows")

    host = MacHost()
    assert host.acquire_single_instance() is True
    lock_path = host.app_dir() / "singleton.lock"
    assert lock_path.is_file()
    assert lock_path.read_text(encoding="utf-8").strip().isdigit()

    other = MacHost()
    assert other.acquire_single_instance() is False
