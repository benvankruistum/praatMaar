"""Tests for the Linux host adapter's XDG paths and instance lock."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import host
from host import APP_NAME
from host._linux import LinuxHost


def test_app_dir_uses_xdg_data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    result = LinuxHost().app_dir()

    assert result == data_home / APP_NAME
    assert result.is_dir()


def test_app_dir_defaults_to_local_share(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda *args, **kwargs: tmp_path)

    assert LinuxHost().app_dir() == tmp_path / ".local" / "share" / APP_NAME


def test_select_returns_linux_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host.sys, "platform", "linux")

    assert isinstance(host._select(), LinuxHost)


@pytest.mark.skipif(sys.platform != "linux", reason="fcntl.flock requires Linux")
def test_single_instance_creates_and_holds_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    first = LinuxHost()

    assert first.acquire_single_instance() is True
    lock_path = first.app_dir() / "singleton.lock"
    assert lock_path.read_text(encoding="utf-8").strip().isdigit()

    assert LinuxHost().acquire_single_instance() is False
