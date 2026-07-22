# Incremental final-from-partial Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bij incrementele transcriptie de laatste `transcript.partial` als finaal gebruiken zodat stop geen volle Whisper-run meer doet (optie C).

**Architecture:** `Opnamesessie` onthoudt `_last_partial_transcript`; incremental loop schrijft die bij elke geslaagde partial; `stop_and_transcribe` kiest partial-finalize vs bestaande chunk-Whisper. Delivery-logica (save/plak/events) blijft één pad.

**Tech Stack:** Python, pytest, bestaande `Opnamesessie` / FakeModel-testpatronen.

---

### Task 1: Tests herzien (TDD red)

**Files:**
- Modify: `tests/test_incremental_transcription.py`

Steps:
1. Herschrijf `test_final_transcription_always_runs_full_whisper_again` → met partial geen extra Whisper; save = partialtekst.
2. Voeg toe: stop zonder partial → wel Whisper.
3. Voeg toe: incremental uit → wel Whisper.
4. Run pytest → red tot implementatie er is.

### Task 2: Opnamesessie — partial als finaal

**Files:**
- Modify: `opnamesessie.py`

Steps:
1. State `_last_partial_transcript`; set in `_incremental_loop`; clear bij start/cancel.
2. Split delivery: `_deliver_transcript(transcript)` uit `_transcribe_audio`.
3. In `stop_and_transcribe`: na worker-stop, als partial → thread die delivery doet zonder Whisper; anders bestaande pad.
4. Pytest groen.

### Task 3: Docs + i18n

**Files:**
- Modify: `docs/user/help.{nl,en,de}.md`, `docs/superpowers/specs/2026-07-19-modules-design.md`, `docs/modules-integration.md`, `locales/{nl,en,de}.json`, module-docstring in `opnamesessie.py`

Steps:
1. Beschrijf: eind = laatste partial; staart na partial kan ontbreken.
2. Commit alles.
