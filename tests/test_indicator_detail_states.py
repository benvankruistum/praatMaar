"""Detailstates (canvas 1a, 02/03/06): ready-cue, voorbereiden, geannuleerd."""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import (
    CANCELLED_DURATION_MS,
    READY_CUE_DURATION_MS,
    countdown_fraction,
)
from ui.app import ensure_app


def _pill(**kwargs):
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator(**kwargs)


def test_ready_cue_is_short() -> None:
    # Canvas 02: "~1,5 s"; 4 s liet de cue te lang hangen.
    assert READY_CUE_DURATION_MS == 1500


def test_countdown_fraction_runs_from_one_to_zero() -> None:
    assert countdown_fraction(0, 2000) == 1.0
    assert countdown_fraction(1000, 2000) == 0.5
    assert countdown_fraction(2000, 2000) == 0.0
    # Buiten bereik netjes geklemd.
    assert countdown_fraction(-10, 2000) == 1.0
    assert countdown_fraction(5000, 2000) == 0.0
    assert countdown_fraction(10, 0) == 0.0


def test_cancelled_reports_remaining_time() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.CANCELLED, "toggle")
    # Direct na de wissel is er bijna de volle tijd over.
    fraction = pill._transient_fraction()
    assert 0.8 <= fraction <= 1.0
    assert pill._hide_timer.interval() == CANCELLED_DURATION_MS


def test_no_countdown_outside_transient_states() -> None:
    pill = _pill()
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert pill._transient_fraction() == 0.0


def test_ready_cue_animates_so_the_ring_can_play() -> None:
    # De ring is een animatie; zonder dit zou slice 8 de repaints wegfilteren.
    pill = _pill()
    pill.show_ready_cue()
    assert pill._is_animated() is True


def test_ready_cue_stops_animating_after_expiry() -> None:
    pill = _pill()
    pill.show_ready_cue()
    pill._transient_expired()
    assert pill._is_animated() is False


def test_preparing_still_shows_its_hint() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.PREPARING, "toggle", "Microfoon openen")
    assert pill._status_hint == "Microfoon openen"
    assert pill._is_animated() is True


def test_ready_cue_uses_the_ok_token() -> None:
    # De groene stip is het enige gebruik van COLOR_OK; zonder deze test zou
    # het token dood gewicht zijn.
    import inspect

    from indicator._qt import RecordingIndicator

    source = inspect.getsource(RecordingIndicator._paint_ready_ring)
    assert "COLOR_OK" in source
