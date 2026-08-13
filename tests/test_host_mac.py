"""Tests voor host._mac (geen echte Mac nodig voor app_dir/plist/paste)."""

from __future__ import annotations

import plistlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from host._launch import dictation_script_path
from host._mac import _AGENT_LABEL, MacHost
from host._mac_paste import _KEY_V, paste_command_v


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
    assert Path(args[-1]) == dictation_script_path()
    assert args[-1].endswith("dictation.py")


def test_dictation_script_path_points_at_repo_root() -> None:
    path = dictation_script_path()
    assert path.name == "dictation.py"
    assert path.is_file()
    assert path.parent == Path(__file__).resolve().parent.parent


def test_paste_posts_command_v_via_quartz(monkeypatch: pytest.MonkeyPatch) -> None:
    down = object()
    up = object()
    create = MagicMock(side_effect=[down, up])
    set_flags = MagicMock()
    post = MagicMock()
    flag_command = object()
    hid_tap = object()

    quartz = types.ModuleType("Quartz")
    quartz.CGEventCreateKeyboardEvent = create
    quartz.CGEventSetFlags = set_flags
    quartz.CGEventPost = post
    quartz.kCGEventFlagMaskCommand = flag_command
    quartz.kCGHIDEventTap = hid_tap
    monkeypatch.setitem(sys.modules, "Quartz", quartz)

    MacHost().paste()

    assert create.call_args_list == [
        ((None, _KEY_V, True),),
        ((None, _KEY_V, False),),
    ]
    assert set_flags.call_args_list == [
        ((down, flag_command),),
        ((up, flag_command),),
    ]
    assert post.call_args_list == [
        ((hid_tap, down),),
        ((hid_tap, up),),
    ]


def test_paste_command_v_helper_matches_host_paste(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct helper and MacHost.paste share the same Quartz sequence."""

    create = MagicMock(side_effect=[object(), object()])
    quartz = types.ModuleType("Quartz")
    quartz.CGEventCreateKeyboardEvent = create
    quartz.CGEventSetFlags = MagicMock()
    quartz.CGEventPost = MagicMock()
    quartz.kCGEventFlagMaskCommand = 0
    quartz.kCGHIDEventTap = 0
    monkeypatch.setitem(sys.modules, "Quartz", quartz)

    paste_command_v()
    assert create.call_count == 2


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
