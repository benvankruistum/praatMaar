"""Tests for indicator position helpers."""

from __future__ import annotations

from indicator._contract import (
    INDICATOR_HEIGHT,
    INDICATOR_WIDTH,
    POSITION_BOTTOM,
    POSITION_LAST,
    POSITION_TOP,
    clamp_indicator_xy,
    normalize_indicator_position,
    preset_indicator_xy,
    sanitize_indicator_xy,
)


def test_normalize_indicator_position() -> None:
    assert normalize_indicator_position("boven-midden") == POSITION_TOP
    assert normalize_indicator_position("onder-midden") == POSITION_BOTTOM
    assert normalize_indicator_position("laatst-geplaatst") == POSITION_LAST
    assert normalize_indicator_position("unknown") == POSITION_TOP
    assert normalize_indicator_position(None, default=POSITION_BOTTOM) == POSITION_BOTTOM


def test_sanitize_indicator_xy() -> None:
    assert sanitize_indicator_xy([10, 20]) == (10, 20)
    assert sanitize_indicator_xy((3, 4)) == (3, 4)
    assert sanitize_indicator_xy(None) is None
    assert sanitize_indicator_xy([1]) is None
    assert sanitize_indicator_xy(["a", "b"]) is None


def test_clamp_indicator_xy() -> None:
    assert clamp_indicator_xy(-10, -5, 800, 600) == (0, 0)
    assert clamp_indicator_xy(900, 700, 800, 600) == (
        800 - INDICATOR_WIDTH,
        600 - INDICATOR_HEIGHT,
    )


def test_preset_indicator_xy_top_and_bottom() -> None:
    top = preset_indicator_xy(POSITION_TOP, 1000, 800)
    bottom = preset_indicator_xy(POSITION_BOTTOM, 1000, 800)
    assert top[0] == (1000 - INDICATOR_WIDTH) // 2
    assert bottom[0] == top[0]
    assert top[1] < bottom[1]
