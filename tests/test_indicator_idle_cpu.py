"""De pill verspilt geen repaints in statische states (canvas 1a: motion).

Het canvas eist "timer stopt volledig in Idle (0% CPU)". Letterlijk stoppen kan
niet: dezelfde timer drenkt ook de statuswachtrij waarmee worker-threads een
nieuwe state doorgeven. Wat wél kan — en het werk is — is niet meer herschilderen
zolang er niets beweegt, en trager pollen.
"""

from __future__ import annotations

from indicator import RecordingState
from ui.app import ensure_app


def _pill():
    from indicator._qt import RecordingIndicator

    app = ensure_app([])
    pill = RecordingIndicator()
    # Zichtbaar maken: _tick schildert alleen bij een zichtbaar venster, dus
    # zonder show() zou elke test slagen zonder iets te bewijzen.
    pill.show()
    app.processEvents()
    assert pill.isVisible()
    return pill


def _count_updates(pill) -> list[int]:
    calls: list[int] = []
    pill.update = lambda *_a, **_k: calls.append(1)  # type: ignore[method-assign]
    return calls


def test_idle_tick_does_not_repaint() -> None:
    from ui.app import ensure_app as _ensure

    pill = _pill()
    # Zonder bestemming verbergt Idle zichzelf; het geval dat telt is de
    # persistente Idle-pill mét bestemming (canvas 01).
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    _ensure([]).processEvents()
    assert pill.isVisible(), "Idle met bestemming moet zichtbaar blijven"

    calls = _count_updates(pill)
    for _ in range(5):
        pill._tick()
    assert calls == [], "Idle animeert niets, dus geen repaints"


def test_recording_tick_repaints_every_frame() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    calls = _count_updates(pill)
    for _ in range(5):
        pill._tick()
    assert len(calls) == 5


def test_transcribing_and_preparing_animate() -> None:
    for state in (RecordingState.TRANSCRIBING, RecordingState.PREPARING):
        pill = _pill()
        pill._apply_state(state, "toggle")
        calls = _count_updates(pill)
        pill._tick()
        assert calls, f"{state} moet animeren"


def test_state_change_repaints_even_when_static() -> None:
    # Een nieuwe state uit de wachtrij moet één keer schilderen, ook als de
    # doelstate zelf statisch is — anders zie je de wissel nooit.
    from indicator._contract import notify_state

    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    calls = _count_updates(pill)
    notify_state(RecordingState.CANCELLED, "toggle")
    pill._tick()
    assert calls, "state-wissel moet een repaint opleveren"


def test_poll_interval_slows_down_in_static_states() -> None:
    from indicator._contract import POLL_INTERVAL_IDLE_MS, POLL_INTERVAL_MS

    assert POLL_INTERVAL_IDLE_MS > POLL_INTERVAL_MS

    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    assert pill._timer.interval() == POLL_INTERVAL_MS
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert pill._timer.interval() == POLL_INTERVAL_IDLE_MS
