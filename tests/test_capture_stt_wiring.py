from modules.capabilities.speech_to_text import TranscriptDeltaReceived
from modules.testing.fake_capture import FakeContinuousCapture
from modules.testing.fake_stt import FakeSpeechToText


def test_stt_subscribes_and_emits_delta():
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda c: "hallo wereld")
    deltas: list = []

    cs = capture.start_session()
    ts = stt.start_session(capture_session_id=cs.session_id, capture=capture)
    stt.subscribe(
        ts.session_id,
        lambda ev: deltas.append(ev) if isinstance(ev, TranscriptDeltaReceived) else None,
    )

    capture.emit_seconds(0.1)
    assert any(isinstance(d, TranscriptDeltaReceived) for d in deltas)
    assert deltas[0].delta.text == "hallo wereld"
