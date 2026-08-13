"""UI-smoke: dicteerpresets vullen model + Whisper-velden."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("PySide6.QtWidgets")

import config
from ui.app import ensure_app
from ui.dialogs.settings import SettingsDialog


def _make_dialog(on_apply) -> SettingsDialog:
    ensure_app([])
    return SettingsDialog(
        parent=None,
        current={
            "model": "small",
            "whisper_beam_size": 5,
            "whisper_vad_filter": True,
            "whisper_vad_min_silence_ms": 300,
            "hotkey": ["shift", "esc"],
        },
        on_apply=on_apply,
        set_capture=None,
        on_retranscribe=None,
        on_parent_retranscribe=None,
    )


def test_preset_fast_fills_model_and_beam() -> None:
    applied: list[dict[str, Any]] = []
    dialog = _make_dialog(applied.append)
    try:
        dialog._apply_preset_to_fields("fast")
        assert dialog.model.currentData() == "base"
        assert dialog.whisper_beam_size.value() == 1
        assert dialog.whisper_vad_filter.isChecked() is True
        assert dialog._preset_buttons["fast"].isChecked() is True

        dialog.whisper_beam_size.setValue(3)
        assert dialog._preset_buttons["fast"].isChecked() is False
        # Dialoog is niet shown → isVisible() blijft False; isHidden() is betrouwbaar.
        assert not dialog._preset_custom_hint.isHidden()

        dialog._apply_preset_to_fields("accurate")
        dialog._save()
        assert len(applied) == 1
        assert applied[0]["model"] == "medium"
        assert applied[0]["whisper_beam_size"] == 5
        assert applied[0]["dictation_preset"] == "accurate"
        assert config.match_dictation_preset(applied[0]) == "accurate"
    finally:
        dialog.close()
