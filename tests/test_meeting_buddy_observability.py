from modules._builtin.meeting_buddy.observability import RecordingObserver, log_event


def test_log_event_strips_transcript_text_fields() -> None:
    observer = RecordingObserver()

    log_event(
        observer,
        "hint_emitted",
        meeting_session_id="m1",
        hint_type="question_open",
        text="GEHEIM",
        transcript_text="OOK GEHEIM",
    )

    assert observer.events == [
        {
            "name": "hint_emitted",
            "meeting_session_id": "m1",
            "hint_type": "question_open",
        }
    ]
    assert observer.names == ["hint_emitted"]
