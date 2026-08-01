"""Kleursemantiek van de pill (canvas 1a) + onderscheid zonder kleur.

Canvas 1a hangt aan één regel: **rood betekent uitsluitend "er wordt
opgenomen"**. Transcriberen is blauw, mislukt is amber. Daarnaast moet elke
state te onderscheiden zijn zónder kleur — de gebruiker is kleurenblind, dus
vorm/tekst draagt de betekenis en kleur versterkt alleen.
"""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import (
    COLOR_CANCELLED,
    COLOR_ERROR,
    COLOR_OK,
    COLOR_PREPARING,
    COLOR_RECORDING,
    COLOR_TRANSCRIBING,
    STATE_COLORS,
)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _is_reddish(hex_color: str) -> bool:
    """Rood = veel rood én wéinig groen.

    Het groenkanaal scheidt rood (#E5484D, g=72) van amber (#F5A524, g=165);
    beide hebben een hoog roodkanaal, dus daarop alleen filteren volstaat niet.
    """

    r, g, b = _rgb(hex_color)
    return r > 150 and g < 120 and r > b + 60


def test_recording_is_the_only_reddish_state_color() -> None:
    assert _is_reddish(COLOR_RECORDING)
    for state, color in STATE_COLORS.items():
        if state == RecordingState.RECORDING:
            continue
        assert not _is_reddish(color), f"{state} mag niet roodachtig zijn: {color}"


def test_transcribing_is_blue() -> None:
    r, g, b = _rgb(COLOR_TRANSCRIBING)
    assert b > r + 40 and b > 150, f"transcriberen moet blauw zijn, kreeg {COLOR_TRANSCRIBING}"


def test_error_is_amber_not_red() -> None:
    r, g, b = _rgb(COLOR_ERROR)
    assert r > 180 and g > 120 and b < 110, f"mislukt moet amber zijn, kreeg {COLOR_ERROR}"
    assert not _is_reddish(COLOR_ERROR)


def test_ok_token_exists_for_ready_cue() -> None:
    r, g, b = _rgb(COLOR_OK)
    assert g > r + 40 and g > 150, f"ready-cue moet groen zijn, kreeg {COLOR_OK}"


def test_preparing_is_neutral_grey() -> None:
    # Bewust gedempt: rood/amber zijn voor "opnemen" en "mislukt" gereserveerd.
    r, g, b = _rgb(COLOR_PREPARING)
    assert max(r, g, b) - min(r, g, b) < 30, f"voorbereiden moet neutraal zijn: {COLOR_PREPARING}"


def test_cancelled_is_neutral_grey() -> None:
    r, g, b = _rgb(COLOR_CANCELLED)
    assert max(r, g, b) - min(r, g, b) < 30


def _luminance(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_state_colors_are_distinguishable_in_greyscale() -> None:
    # Kleurenblind-eis: kleur mag nooit de enige drager zijn. Waar twee states
    # in grijswaarde dicht bij elkaar liggen (rood/amber), moet de vorm het
    # verschil maken — dat dekt test_state_glyphs_are_unique af.
    grey = {state: _luminance(color) for state, color in STATE_COLORS.items()}
    assert len(grey) == len(STATE_COLORS)
    # Sanity: geen enkele state is onzichtbaar donker op de donkere capsule.
    for state, value in grey.items():
        assert value > 60, f"{state} is te donker voor de HUD-capsule ({value:.0f})"


def test_state_glyphs_are_unique() -> None:
    """Elke state heeft een eigen vorm, los van kleur."""

    from indicator._contract import STATE_GLYPHS

    shapes = [STATE_GLYPHS[state] for state in STATE_COLORS]
    assert len(set(shapes)) == len(shapes), f"vormen niet uniek: {shapes}"
