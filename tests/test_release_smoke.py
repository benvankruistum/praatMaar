"""Release and import smoke checks for packaged builds."""

from __future__ import annotations

import importlib


def test_builtin_modules_import_cleanly() -> None:
    modules = [
        "modules._builtin.meeting_buddy.orchestrator",
        "modules._builtin.meeting_buddy.session_controller",
        "modules._builtin.meeting_buddy.transcript_processor",
        "modules._builtin.meeting_buddy.hint_coordinator",
        "modules._builtin.audio_capture",
        "modules._builtin.speech_to_text",
    ]
    for module_name in modules:
        importlib.import_module(module_name)


def test_meeting_buddy_defaults_yaml_loads() -> None:
    from modules._builtin.meeting_buddy.config import MeetingBuddyConfig

    defaults = MeetingBuddyConfig.defaults()
    assert defaults.max_visible_hints == 3
    assert defaults.max_audio_buffer_duration_s >= defaults.max_whisper_queue_duration_s
