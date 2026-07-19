from modules.capabilities.continuous_capture import (
    CAPABILITY_ID,
    AudioChunk,
    ContinuousCaptureCapability,
)


def test_capability_id():
    assert CAPABILITY_ID == "audio.continuous_capture"


def test_audio_chunk_is_frozen():
    chunk = AudioChunk(
        session_id="c1",
        chunk_id="1",
        start_ms=0,
        end_ms=100,
        sample_rate=16000,
        pcm_f32=b"",
        source="microphone",
    )
    assert chunk.session_id == "c1"
    try:
        chunk.session_id = "x"  # type: ignore[misc]
        raise AssertionError("expected frozen")
    except Exception:
        pass


def test_protocol_methods_exist():
    assert hasattr(ContinuousCaptureCapability, "start_session")
    assert hasattr(ContinuousCaptureCapability, "subscribe")
    assert hasattr(ContinuousCaptureCapability, "stop_session")
    assert hasattr(ContinuousCaptureCapability, "get_status")
