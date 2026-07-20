"""Tray-icoon: uitroepteken bij actie vereist."""

from __future__ import annotations

from indicator import RecordingState
from tray import _draw_attention_badge, _make_icon


def test_attention_badge_changes_icon_pixels() -> None:
    base = _make_icon((32, 33, 36, 255))
    badged = _draw_attention_badge(base)
    assert base.size == badged.size
    assert base.tobytes() != badged.tobytes()


def test_tray_attention_composes_on_idle_state() -> None:
    from tray import TrayIcon

    tray = TrayIcon(
        on_quit=lambda: None,
        on_settings=lambda: None,
        on_destinations=lambda: None,
        on_modules=lambda: None,
        on_help=lambda: None,
    )
    idle = tray._icons[RecordingState.IDLE]
    tray.set_attention_needed(True)
    assert tray._icon_for(RecordingState.IDLE).tobytes() != idle.tobytes()
    tray.set_attention_needed(False)
    assert tray._icon_for(RecordingState.IDLE).tobytes() == idle.tobytes()
