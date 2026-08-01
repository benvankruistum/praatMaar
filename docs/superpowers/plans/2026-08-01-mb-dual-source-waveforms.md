# Meeting Buddy dual source waveforms — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or implement
> directly in-session). Steps use TDD.

**Goal:** Overlay shows separate Mic / Meeting bar-waveforms fed from pre-mix RMS.

**Tech:** `indicator/_contract.py` dual buffers · `audio_capture.py` push ·
`meeting_buddy/overlay.py` paint · locales · pytest.

## File map

| File | Role |
|------|------|
| `indicator/_contract.py` | `push_mic_level`, `push_loopback_level`, snapshots, reset |
| `indicator/__init__.py` | Re-export if useful for tests |
| `modules/_builtin/audio_capture.py` | Push pre-mix RMS; reset on session start |
| `modules/_builtin/meeting_buddy/overlay.py` | Dual waveform rows + warning |
| `locales/{nl,en,de}.json` | Mic / Meeting labels (+ short warn if needed) |
| `tests/test_indicator_contract.py` | Buffer API |
| `tests/test_audio_capture_*.py` or new | Pre-mix push (unit with mocks) |
| `tests/test_meeting_buddy_overlay.py` | Overlay rows / unavailable state |

## Tasks

### Task 1: Contract buffers (TDD)

1. Failing tests: push mic/loopback independently; reset clears both; maxlen = NUM_BARS
2. Implement in `_contract.py`
3. Green

### Task 2: Capture wiring (TDD)

1. Test or extend existing capture mix test: when flushing mixed chunks, mic and
   loopback RMS are pushed separately; mixed still goes to `push_level`
2. Reset source levels when capture session starts
3. Green

### Task 3: Overlay UI (TDD)

1. Test: overlay exposes/finds Mic + Meeting waveform host when capture active
2. Test: loopback unavailable → meeting strip present + warning text visible
3. Implement `_SourceLevels` (or similar) widget + poll from existing/`QTimer` 50–100 ms
4. Green + manual: start MB with/without loopback audio

## Spec self-review

- No placeholders; approach A only; overlay-only placement locked
- Warning behaviour matches brainstorm choice 3
- Pill mix waveform unchanged
