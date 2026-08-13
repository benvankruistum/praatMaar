"""Characterization tests before/alongside composition-root moves (P2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import dictation
from dicteercyclus.delivery import transcript_chars_message
from modules._contract import CycleEvent, CycleEventType
from modules.journal import EventJournal


def test_journal_redacts_transcript_content(tmp_path: Path) -> None:
    import json

    journal_path = tmp_path / "events.jsonl"
    journal = EventJournal(path=journal_path)
    journal.write(
        CycleEvent(
            type=CycleEventType.CYCLE_COMPLETED,
            session_id="s1",
            transcript="vertrouwelijke burgertekst",
        )
    )
    raw = journal_path.read_text(encoding="utf-8")
    payload = json.loads(raw.strip())
    assert "vertrouwelijke" not in raw
    assert payload["transcript_chars"] == len("vertrouwelijke burgertekst")
    assert "transcript" not in payload


def test_transcript_chars_message_has_no_body() -> None:
    secret = "geheim-paspoortnummer-123"
    message = transcript_chars_message(secret)
    assert secret not in message
    assert str(len(secret)) in message


def test_apply_settings_updates_session_mic_and_mode(monkeypatch) -> None:
    """Parity: apply_settings syncs session fields and triggers mic refresh."""

    monkeypatch.setattr(dictation.config, "save_config", lambda _cfg: None)
    monkeypatch.setattr(dictation.host, "set_autostart", lambda _v: None)
    monkeypatch.setattr(dictation.host, "is_autostart_enabled", lambda: False)
    monkeypatch.setattr(dictation, "_refresh_mic_attention", lambda: None)

    session = dictation.ensure_session()
    session.refresh_input_device = MagicMock()
    session.stop_audio_stream = MagicMock()
    session.warmup_microphone = MagicMock()

    indicator = MagicMock()
    settings = dictation.current_settings()
    settings["mode"] = "ptt" if settings.get("mode") == "toggle" else "toggle"
    settings["microphone_device"] = 99
    settings["warm_microphone"] = False

    dictation.apply_settings(settings, indicator)

    assert session.mode == settings["mode"]
    assert session.microphone_device == 99
    session.refresh_input_device.assert_called()
