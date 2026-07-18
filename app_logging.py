"""
Bestandslogging voor praatMaar.

Onder `pythonw` of een windowed PyInstaller-build is er geen console: `print`
verdwijnt dan stil. Deze module schrijft alle stdout/stderr-uitvoer (én
standaard `logging`) naar `%APPDATA%\\praatMaar\\praatMaar.log` (via
`host.app_dir()`), zodat fouten altijd terug te vinden zijn.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO, cast

import host

_LOG_NAME = "praatMaar.log"
_configured = False


class _Tee:
    """Schrijft naar het originele stream (als aanwezig) én naar het logbestand."""

    def __init__(self, primary: TextIO | None, secondary: TextIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, data: str) -> int:
        if self._primary is not None:
            try:
                self._primary.write(data)
            except OSError:
                pass
        try:
            self._secondary.write(data)
            self._secondary.flush()
        except OSError:
            pass
        return len(data)

    def flush(self) -> None:
        if self._primary is not None:
            try:
                self._primary.flush()
            except OSError:
                pass
        try:
            self._secondary.flush()
        except OSError:
            pass

    def isatty(self) -> bool:
        if self._primary is not None:
            try:
                return bool(self._primary.isatty())
            except OSError:
                return False
        return False

    def fileno(self) -> int:
        if self._primary is not None:
            return self._primary.fileno()
        raise OSError("geen fileno voor tee zonder primaire stream")

    @property
    def encoding(self) -> str:
        if self._primary is not None and getattr(self._primary, "encoding", None):
            return cast(str, self._primary.encoding)
        return "utf-8"

    def __getattr__(self, name: str) -> Any:
        if self._primary is not None:
            return getattr(self._primary, name)
        raise AttributeError(name)


def log_path() -> Path:
    """Pad van het logbestand (`…\\praatMaar\\praatMaar.log`)."""

    return host.app_dir() / _LOG_NAME


def setup_logging() -> Path:
    """
    Configureert bestandslogging en tee't stdout/stderr naar hetzelfde bestand.

    Idempotent: een tweede aanroep doet niets. Geeft het logpad terug.
    """

    global _configured
    if _configured:
        return log_path()

    directory = host.app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _LOG_NAME

    log_file = path.open("a", encoding="utf-8", errors="replace")
    log_file.write(
        f"\n--- praatMaar start {datetime.now().isoformat(timespec='seconds')} ---\n"
    )
    log_file.flush()

    sys.stdout = cast(TextIO, _Tee(getattr(sys, "stdout", None), log_file))
    sys.stderr = cast(TextIO, _Tee(getattr(sys, "stderr", None), log_file))

    root = logging.getLogger()
    already = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")) == path.resolve()
        for handler in root.handlers
    )
    if not already:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    _configured = True
    return path
