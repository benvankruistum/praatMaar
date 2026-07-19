from modules.capabilities import semantic_analysis as sa
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID,
    TranscriptDelta,
)


def test_ids():
    assert CAPABILITY_ID == "transcription.speech_to_text"
    assert sa.CAPABILITY_ID == "ai.semantic_analysis"


def test_delta_fields():
    d = TranscriptDelta(
        session_id="t1",
        sequence=1,
        start_ms=0,
        end_ms=3000,
        text="hallo",
        is_final=True,
        confidence=0.9,
    )
    assert d.sequence == 1
    assert d.is_final is True
