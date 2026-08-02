# Meeting Buddy live samenvatting (bullets + delta + journal) Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD. Steps use checkbox syntax.

**Goal:** Live samenvatting als 3–5 bullets, gevoed met transcript-delta, gesynchroniseerd naar `## Samenvatting` in het meeting-`.md`.

**Architecture:** `LiveSummaryCoordinator` buffert alleen nieuwe final-STT sinds de vorige succesvolle run; `local-llm` prompt levert bullets; overlay toont 1:1; `TranscriptJournal` upsert `## Samenvatting` tussen Agenda en Transcript.

**Tech Stack:** Python, bestaande `ai.semantic_analysis` / Ollama provider, PySide6 overlay, pytest.

**Spec:** [2026-08-02-meeting-buddy-live-summary-bullets-design.md](../specs/2026-08-02-meeting-buddy-live-summary-bullets-design.md)

## Global Constraints

- Geen bullet-categorieën; geen eindpass bij stop; geen contractversie-bump
- Drempels blijven AND (`interval_s` + `min_new_chars`)
- Privacy: alles lokaal

## File map

| File | Rol |
|------|-----|
| `modules/_builtin/meeting_buddy/live_summary.py` | Delta-buffer i.p.v. volle transcript |
| `modules/_builtin/local_llm/provider.py` | Prompt → 3–5 `- ` bullets |
| `modules/_builtin/meeting_buddy/overlay.py` | `summary_points` / normalisatie |
| `modules/_builtin/meeting_buddy/transcript_journal.py` | upsert `## Samenvatting` |
| `modules/_builtin/meeting_buddy/orchestrator.py` | journal bij summary-callback |
| `tests/test_meeting_buddy_live_summary.py` | delta + thresholds |
| `tests/test_meeting_buddy_transcript_journal.py` (of bestaand) | samenvatting-sectie |
| `tests/test_local_llm.py` | prompt/kind ongewijzigd contractueel |

## Tasks

### Task 1: Delta-buffer coordinator

- [x] Failing tests: `transcript` in request = alleen nieuwe tekst; previous = vorige summary
- [x] Implement delta in `live_summary.py` (cap ~8–12k)
- [x] Bestaande interval/chars-tests groen

### Task 2: Bullet normalisatie + overlay

- [x] Tests voor `summary_points` / shared normalize helper (3–5 bullets)
- [x] Overlay gebruikt genormaliseerde lijst 1:1

### Task 3: Prompt `running_summary`

- [x] Update system/user prompt in `provider.py` naar 3–5 bullets
- [x] Unit test blijft kind/contract dekken

### Task 4: Journal `## Samenvatting`

- [x] Tests insert/replace tussen Agenda en Transcript
- [x] `TranscriptJournal.update_summary(text)`
- [x] Orchestrator: bij `_on_live_summary` journal updaten

### Task 5: Verify

- [x] `pytest` voor geraakte tests
- [x] `ruff check` / format op gewijzigde files
