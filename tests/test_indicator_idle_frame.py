"""Idle-state (canvas 1a, 01): padsegmenten, regelorde en toets-chips."""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import destination_path_label, hotkey_chips
from ui.app import ensure_app


def test_path_label_keeps_last_two_segments() -> None:
    assert destination_path_label(r"D:\Werk\Opnames\Klantgesprekken") == "Opnames / Klantgesprekken"
    assert destination_path_label("/home/ben/opnames/klanten") == "opnames / klanten"


def test_path_label_handles_short_paths() -> None:
    assert destination_path_label(r"D:\Opnames") == "D: / Opnames"
    assert destination_path_label("Opnames") == "Opnames"


def test_path_label_empty_input() -> None:
    assert destination_path_label("") == ""
    assert destination_path_label(None) == ""


def test_path_label_uses_mid_ellipsis_for_long_segments() -> None:
    long_path = r"D:\Werk\Hele-lange-projectmap-naam-die-niet-past\Klantgesprekken-Q3-2026"
    label = destination_path_label(long_path, limit=34)
    assert len(label) <= 34
    assert "…" in label
    # Midden-ellipsis: begin én einde blijven leesbaar (het einde is het meest
    # onderscheidend bij paden).
    assert label.startswith("Hele")
    assert label.endswith("2026")


def test_path_label_strips_trailing_separators() -> None:
    assert destination_path_label("D:\\Werk\\Opnames\\") == "Werk / Opnames"


def test_hotkey_chips_splits_on_plus() -> None:
    assert hotkey_chips("Ctrl+Alt+R") == ["Ctrl", "Alt", "R"]
    assert hotkey_chips("ctrl + shift + f9") == ["ctrl", "shift", "f9"]


def test_hotkey_chips_empty() -> None:
    assert hotkey_chips(None) == []
    assert hotkey_chips("") == []
    assert hotkey_chips("  ") == []


def _pill():
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator()


def test_idle_keeps_record_button_next_to_dismiss() -> None:
    # Bewuste afwijking van het canvas: de ● blijft, zodat starten zonder
    # sneltoets mogelijk blijft.
    pill = _pill()
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    record, dismiss = pill._record_rect(), pill._dismiss_rect()
    assert not record.intersects(dismiss)
    assert record.right() < dismiss.left()
    assert record.width() == 32 and dismiss.width() == 32


def test_pill_accepts_destination_path() -> None:
    pill = _pill()
    pill.set_destination("Klantgesprekken", path=r"D:\Werk\Opnames\Klantgesprekken")
    assert pill._destination_path == r"D:\Werk\Opnames\Klantgesprekken"
    # Naam blijft leidend voor de eerste regel/sticky-logica.
    assert pill._dest_pill.name == "Klantgesprekken"


def test_full_path_is_available_as_tooltip() -> None:
    # Bij 340 px past naam én pad niet op één regel (gemeten: ~129 px ruimte,
    # naam kost al 86 px). De tooltip geeft het volle pad zonder ruimte te kosten.
    pill = _pill()
    pill.set_destination("Klantgesprekken", r"D:\Werk\Opnames\Klantgesprekken")
    tip = pill.toolTip()
    assert "Klantgesprekken" in tip
    assert r"D:\Werk\Opnames\Klantgesprekken" in tip


def test_tooltip_falls_back_to_name_without_path() -> None:
    pill = _pill()
    pill.set_destination("Klantgesprekken")
    assert pill.toolTip() == "Klantgesprekken"
