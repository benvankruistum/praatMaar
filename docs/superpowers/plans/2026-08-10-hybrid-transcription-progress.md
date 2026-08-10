# Hybride transcriptie-voortgang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or
> subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tijdens finale Whisper-runs (full + chunk-staart) hybride pill-voortgang
tonen: tijdschatting (audio × RTF) + `max` met segment-%, zodat de balk niet
~80% van de wachttijd op `0%` blijft — volgens
`docs/superpowers/specs/2026-08-10-hybrid-transcription-progress-design.md`.

**Architecture:** Pure helpers + `TranscriptionProgressTicker` (daemon thread →
`set_transcription_progress`). `Opnamesessie._transcribe_audio` en
`_finalize_chunk_transcript` starten/stoppen de ticker; full-pad meldt
segment-floors.

**Tech Stack:** Python 3, threading, pytest, bestaande `indicator._contract`.

## Global Constraints

- Geen commits op `main`; branch `cursor/hybrid-transcription-progress`.
- Geen RTF-learning / ETA-labels in v1.
- Geen progress tijdens RECORDING-partials.
- Ticker altijd stoppen in `finally`.

## File map

| File | Rol |
|------|-----|
| `transcription_progress.py` | Pure % + `TranscriptionProgressTicker` |
| `tests/test_transcription_progress.py` | Helpers + ticker |
| `opnamesessie.py` | Wire ticker in full + chunk-finalize |
| `tests/test_hybrid_transcription_progress.py` | Sessie-integratie (trage mock) |
| `docs/superpowers/specs/2026-07-22-transcription-progress-design.md` | Status: superseded note |
| `CHANGELOG.md` | Unreleased UX-note |

---

### Task 1: Pure helpers + ticker (TDD)

**Files:**
- Create: `transcription_progress.py`
- Modify: `tests/test_transcription_progress.py`

**Interfaces:**
- `DEFAULT_RTF = 0.4`
- `MAX_TICK_PERCENT = 95`
- `time_based_percent(elapsed_s, audio_s, *, rtf=DEFAULT_RTF) -> int`  # 1–95
- `hybrid_percent(time_percent, segment_percent: int | None) -> int`
- `class TranscriptionProgressTicker`: `start()`, `note_segment(percent)`, `stop(final: int | None = 100)`

- [x] **Step 1:** Tests voor time/hybrid clamps + ticker beweegt tijdens sleep.
- [x] **Step 2:** Implementatie tot groen.
- [x] **Step 3:** Commit `feat: hybrid transcription progress helpers`.

---

### Task 2: Wire Opnamesessie

**Files:**
- Modify: `opnamesessie.py`
- Create: `tests/test_hybrid_transcription_progress.py`

- [x] **Step 1:** Failing integratietest: trage mock → samples in 1–95 vóór 100.
- [x] **Step 2:** `_transcribe_audio` + `_finalize_chunk_transcript` gebruiken ticker.
- [x] **Step 3:** Tests groen; commit `feat: hybrid progress during final Whisper`.

---

### Task 3: Docs

**Files:**
- Modify: old progress design status + `CHANGELOG.md`

- [x] **Step 1:** Supersede-note + Unreleased bullet.
- [x] **Step 2:** Commit `docs: hybrid transcription progress spec`.
