"""Shared launch helpers for Host autostart adapters."""

from __future__ import annotations

from pathlib import Path


def dictation_script_path() -> Path:
    """Resolve repo-root ``dictation.py`` relative to the ``host`` package."""

    return Path(__file__).resolve().parent.parent / "dictation.py"
