"""Logbestand: begrensde retentie via rotatie bij opstarten."""

from __future__ import annotations

from pathlib import Path

import app_logging


def test_rotate_log_moves_oversized_log_to_backup(tmp_path: Path) -> None:
    # AVG: praatMaar.log groeide onbegrensd (append-only, met o.a.
    # transcriptuitvoer via de stdout-tee). Rotatie bij opstarten begrenst
    # de bewaartermijn tot maximaal twee bestanden.
    log = tmp_path / "praatMaar.log"
    log.write_text("x" * (app_logging._MAX_LOG_BYTES + 1), encoding="utf-8")

    app_logging._rotate_if_oversized(log)

    backup = tmp_path / "praatMaar.log.1"
    assert backup.exists()
    assert not log.exists() or log.stat().st_size == 0


def test_rotate_log_keeps_small_log(tmp_path: Path) -> None:
    log = tmp_path / "praatMaar.log"
    log.write_text("klein", encoding="utf-8")

    app_logging._rotate_if_oversized(log)

    assert log.read_text(encoding="utf-8") == "klein"
    assert not (tmp_path / "praatMaar.log.1").exists()


def test_rotate_log_replaces_previous_backup(tmp_path: Path) -> None:
    log = tmp_path / "praatMaar.log"
    backup = tmp_path / "praatMaar.log.1"
    backup.write_text("oud", encoding="utf-8")
    log.write_text("x" * (app_logging._MAX_LOG_BYTES + 1), encoding="utf-8")

    app_logging._rotate_if_oversized(log)

    assert backup.exists()
    assert backup.read_text(encoding="utf-8") != "oud"
