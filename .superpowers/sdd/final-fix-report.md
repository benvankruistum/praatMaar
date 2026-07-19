# Final whole-branch review fixes

## 2026-07-19

- Wired `max_audio_buffer_duration_s` and `max_whisper_queue_duration_s` from
  Meeting Buddy YAML config into per-session capture and STT configuration.
- Made STT queue limits session-specific and verified the capture ring buffer
  honors its configured duration.
- Added explicit capture failure signaling, a Meeting Buddy reconnect action,
  session rebinding, overlay reconnect control, and `capture_restart` logging.
- Deduplicated highly similar open questions and candidate actions from
  overlapping final transcript windows.
- Logged confirmed hints as dismissed, made fake STT detach from capture on
  stop, and removed the unused `HintStatus` re-export.

Verification:

- Focused Meeting Buddy/capture/STT tests: `35 passed`.
- Complete test suite: `213 passed, 1 skipped`.
- Ruff check: passed.
