"""Tests voor config-persistentie met een tijdelijke datamap."""

from __future__ import annotations

from pathlib import Path

import config


def test_load_config_missing_returns_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    assert config.load_config() == {}


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    settings = {"model": "small", "auto_paste": True, "hotkey": ["ctrl", "space"]}
    config.save_config(settings)
    assert config.config_path() == tmp_path / "config.json"
    assert config.config_path().is_file()
    assert config.load_config() == settings


def test_load_config_invalid_json_returns_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    (tmp_path / "config.json").write_text("{niet-json", encoding="utf-8")
    assert config.load_config() == {}


def test_ensure_app_data_dirs_creates_standard_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path)
    assert config.ensure_app_data_dirs() == tmp_path
    for name in ("transcripts", "recovery", "events", "inbox"):
        assert (tmp_path / name).is_dir()
