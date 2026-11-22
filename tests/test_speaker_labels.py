"""Anonieme sprekerregels voor de definitieve transcriptie."""

from __future__ import annotations

from types import SimpleNamespace

from dicteercyclus.speaker_labels import format_transcript_with_speakers


class _Provider:
    def assign_speaker(self, segment):
        speaker = "spk_1" if (segment.start_ms or 0) < 1000 else "spk_2"
        return SimpleNamespace(speaker_id=speaker)


def test_groups_consecutive_speakers() -> None:
    notes = [
        {"kept": True, "text": "Hallo", "start_s": 0.1, "end_s": 0.4},
        {"kept": True, "text": "daar", "start_s": 0.5, "end_s": 0.8},
        {"kept": True, "text": "Ik ook", "start_s": 1.2, "end_s": 1.6},
        {"kept": False, "text": "weg", "start_s": 2.0, "end_s": 2.2},
    ]
    labeled = format_transcript_with_speakers(_Provider(), "sessie", notes)
    assert labeled == "[spk_1] Hallo daar\n[spk_2] Ik ook"


def test_unknown_speaker_stays_unbracketed() -> None:
    class Unknown:
        def assign_speaker(self, segment):
            return SimpleNamespace(speaker_id="unknown")

    notes = [{"kept": True, "text": "Alleen tekst", "start_s": 0.0, "end_s": 0.4}]
    assert format_transcript_with_speakers(Unknown(), "sessie", notes) == "Alleen tekst"


def test_empty_notes_return_none() -> None:
    assert format_transcript_with_speakers(_Provider(), "sessie", []) is None
