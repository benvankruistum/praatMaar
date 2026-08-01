# Chunk-transcriptie-pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vervang volle-buffer incremental Whisper door een chunk-pipeline (fixed/vad/hybrid) met overlap-ontdubbeling, snelle stop via concatenatie, pill-LEDs en modules-UI — volgens `docs/superpowers/specs/2026-08-01-chunk-transcription-pipeline-design.md`.

**Architecture:** Pure helpers in `chunk_transcription.py` (knipbesluit + tekst-ontdubbeling). `Opnamesessie` houdt een sample-cursor bij, transcribeert alleen nieuwe open-chunk-audio (+ overlap), emitteert partials als concatenatie, en levert bij stop die concatenatie (+ staart) zonder volle her-run. Indicator-contract + Qt-pill tonen twee LED’s. Config/modules/locales/help volgen.

**Tech Stack:** Python 3, pytest, numpy (RMS), PySide6 pill, bestaande `SharedWhisper` / `CycleEvent`.

## Global Constraints

- Geen app afsluiten/herstarten tenzij de gebruiker dat vraagt.
- Geen commits op `main`; werk op `cursor/chunk-transcription-pipeline`.
- Conservatieve ontdubbeling: liever dubbel dan tekst weggooien (≥2 woorden match).
- Overlap intern 1,5 s; hard cap in vad-modus = `incremental_chunk_seconds`.
- Recovery: hele sessie-WAV bij stop/staart-fout; geen recovery-spam per mid-chunk-falen.
- Pill-design: donkere HUD, LED-kleuren uit bestaande tokens (VAD ≈ meeting-blauw, tijd ≈ `#FFB020`).

## File map

| File | Rol |
|------|-----|
| `chunk_transcription.py` | Pure: `dedupe_overlap_text`, `decide_chunk_cut`, stilte-scan |
| `opnamesessie.py` | Chunk-worker, cursor, stop-pad chunk/fallback |
| `indicator/_contract.py` | LED state + `signal_chunk_trigger` / `set_chunk_leds_enabled` |
| `indicator/_qt.py` | Teken twee LED’s in recording layout |
| `indicator/__init__.py` | Re-exports |
| `dictation.py` | Config laden/opslaan/toepassen |
| `ui/dialogs/modules.py` | Modus + VAD-ms + chunk-s controls |
| `locales/{nl,en,de}.json` | Copy |
| `docs/user/help.{nl,en,de}.md` | Help + naad-waarschuwing |
| `docs/design/modules.md` | Globale-optie tekst |
| `tests/test_chunk_transcription.py` | Pure helpers |
| `tests/test_incremental_transcription.py` | Sessie-gedrag (herschrijven) |
| `tests/test_indicator_contract.py` | LED-signalen |

---

### Task 1: Pure helpers (TDD)

**Files:**
- Create: `chunk_transcription.py`
- Create: `tests/test_chunk_transcription.py`

**Interfaces:**
- Produces:
  - `OVERLAP_SECONDS: float = 1.5`
  - `dedupe_overlap_text(previous: str, new_text: str, *, min_words: int = 2) -> str`
  - `trailing_silence_seconds(rms_per_frame: list[float], *, frame_seconds: float, silence_rms: float) -> float`
  - `decide_chunk_cut(*, mode: str, open_seconds: float, trailing_silence_seconds: float, chunk_seconds: float, vad_ms: int, min_seconds: float) -> str | None`  # `"vad"` | `"fixed"` | `None`

- [ ] **Step 1:** Tests voor dedupe (match / geen match / te kort), decide_cut (fixed/vad/hybrid/hard-cap), trailing silence.
- [ ] **Step 2:** Implementatie tot groen.
- [ ] **Step 3:** Commit `feat: chunk transcription pure helpers`.

---

### Task 2: Indicator chunk-LEDs

**Files:**
- Modify: `indicator/_contract.py`, `indicator/__init__.py`, `indicator/_qt.py`
- Test: `tests/test_indicator_contract.py`

**Interfaces:**
- Produces: `set_chunk_leds_enabled(bool)`, `signal_chunk_trigger(reason: Literal["vad","fixed"])`, `chunk_led_snapshot() -> tuple[bool, bool, bool]` (enabled, vad_on, fixed_on); hit ~0.8 s.
- Consumes: `COLOR_MEETING_DOT` / `COLOR_TRANSCRIBING`, `MUTED_COLOR`.

- [ ] **Step 1:** Contract-tests voor enable + flash.
- [ ] **Step 2:** Contract + Qt paint tussen waveform en modus-tag.
- [ ] **Step 3:** Commit `feat: pill chunk-trigger LEDs`.

---

### Task 3: Opnamesessie chunk-pipeline

**Files:**
- Modify: `opnamesessie.py`
- Modify: `tests/test_incremental_transcription.py`

**Interfaces:**
- Consumes: helpers uit Task 1; `signal_chunk_trigger` / `set_chunk_leds_enabled`.
- Constructor params: `incremental_chunk_mode`, `incremental_vad_ms`, `incremental_chunk_seconds` (defaults hybrid/2000/30); deprecate interval als poll (~0.25 s).
- Stop: als `_chunk_transcripts` non-empty → staart-Whisper + deliver concatenatie (`path="chunk"`); anders volle run.

- [ ] **Step 1:** Herschrijf tests: stop zonder extra volle run na chunks; partials groeien via concatenatie; module uit = volle run; geen chunks = fallback.
- [ ] **Step 2:** Vervang `_incremental_loop`; cursor + overlap; stop-pad; recovery bij staart-fout met deels resultaat.
- [ ] **Step 3:** Commit `feat: chunk pipeline in Opnamesessie`.

---

### Task 4: Config + Modules-UI + docs

**Files:**
- Modify: `dictation.py`, `ui/dialogs/modules.py`, `locales/*.json`, `docs/user/help.*.md`, `docs/design/modules.md`
- Test: bestaande dialog/config tests indien aanwezig; anders smoke via modules save keys.

- [ ] **Step 1:** Wire settings round-trip.
- [ ] **Step 2:** Modules controls + i18n/help/designbrief.
- [ ] **Step 3:** Commit `feat: chunk pipeline settings and docs`.

---

### Task 5: Verify

- [ ] Run: `pytest tests/test_chunk_transcription.py tests/test_incremental_transcription.py tests/test_indicator_contract.py tests/test_opnamesessie.py -q`
- [ ] Run: `ruff check` op gewijzigde files
- [ ] **Niet** de draaiende app herstarten.
