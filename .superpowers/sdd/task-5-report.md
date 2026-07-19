# Task 5 report — SharedWhisper busy-aware access + speech-to-text

## Status

Implemented on `feat/meeting-buddy-mvp`.

## Changes

- Added `SharedWhisper.try_locked_model(timeout=0.0)` as a context manager that
  yields the shared model when immediately available and `None` while dictation
  owns the lock.
- Added `IncrementalSpeechToText`, which subscribes to
  `AudioChunkReceived`, maps capture sessions to transcription sessions, and
  emits final `TranscriptDeltaReceived` events.
- Kept Whisper acquisition non-blocking. Busy audio remains in a bounded FIFO;
  overflow drops the oldest unprocessed audio, emits `TranscriptGap`, and marks
  the session `DELAYED`.
- Reacquires the Whisper lock between queued chunks so dictation can win at
  every chunk boundary.
- Contains transcription and subscriber exceptions inside the STT path so they
  cannot propagate into capture or dictation.
- Reuses capture's 3000 ms windows with 500 ms overlap. Gap ranges exclude
  audio retained by the overlapping successor window.
- Added `SpeechToTextModule` (`id = "speech-to-text"`, enabled by default),
  capability registration/cleanup, built-in registry registration, and NL/EN/DE
  locale strings.
- Added dependency injection through `transcribe_fn`, so tests do not load a
  real Whisper model.

## TDD evidence

1. `tests/test_shared_whisper_try_lock.py` failed with missing
   `try_locked_model`; it passed after the minimal lock implementation.
2. `tests/test_speech_to_text_backpressure.py` initially failed during
   collection because the STT implementation did not exist; the backpressure
   test passed after implementing the engine.
3. The built-in registry test failed because `speech-to-text` was absent, then
   passed after registration.

Coverage includes busy/available lock access, overflow gaps and delayed status,
successful final deltas, fail-soft transcription errors, and built-in module
registration.

## Verification

- `python -m pytest -q` — 165 passed, 1 skipped.
- `python -m ruff check .` — all checks passed.
- `python -m ruff format --check .` — 78 files already formatted.
- IDE diagnostics on changed Python files — no errors.

## Self-review

- Fixed concurrent drain risk by serializing each session's queue drain and
  removing chunks from the queue before inference.
- Avoided publishing callbacks while holding the engine state lock.
- Corrected overflow gap timestamps for overlapping capture windows.
- Updated older module-isolation tests to explicitly disable the new
  default-enabled module.

## Remaining concerns

- Queue draining is event-driven; while capture is active, each incoming window
  retries the non-blocking lock. There is no independent retry worker after
  capture stops, which is acceptable for this continuous-capture MVP but may
  matter if later requirements retain queued audio after session stop.
- Confidence is `1.0` for MVP deltas because Faster-Whisper's segment metadata
  is not yet normalized into the capability confidence contract.

## Commit

`Add speech-to-text capability with SharedWhisper backpressure.`
