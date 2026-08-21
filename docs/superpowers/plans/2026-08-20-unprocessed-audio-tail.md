# Unprocessed audio-staart Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task (of executing-plans). Steps: TDD. Geen commits op `main`; commit alleen als de gebruiker dat vraagt.

**Goal:** Whisper niet de laatste 6 s van een knip; live toont alleen confirmed tekst; `committed` schuift alleen na geslaagde Whisper.

**Spec:** [2026-08-20-unprocessed-audio-tail-design.md](../specs/2026-08-20-unprocessed-audio-tail-design.md) (akkoord).

**ADR:** n/a

**Architecture:** Pure helper `commit_window` (samples, `available = cut_end - committed`). Cut-cursor plant 20 s-cadans; committed-cursor markeert getranscribeerde audio. Job draagt `commit_end_sample`; bij falen blijft `committed`. Stop fluistert `[0,end]` of `[committed-overlap,end]`.

**Tech stack:** Python, pytest, bestaande `Opnamesessie` / `IncrementalMixin` / `SharedWhisper`.

## Global constraints

- Branch: huidige feature-branch, nooit `main`
- Geen app-herstart tenzij de gebruiker vraagt
- Geen prefix-dedupe `pa`/`paard`; geen `merge_timed_chunk` wiren
- Live: alleen confirmed (optie A)
- Hold-drempel: `available >= tail_samples + 2 * overlap_samples`
- `processing_ratio = whisper_s / window_s` per job loggen

## File map

| File | Rol |
|------|-----|
| `chunk_transcription.py` | `UNPROCESSED_TAIL_SECONDS`, `CommitWindow`, `commit_window` |
| `tests/test_chunk_transcription.py` | Pure venster-tests (reeks, grens, korte available) |
| `dicteercyclus/incremental.py` | Job + enqueue-venster + committed bij success + ratio-log |
| `dicteercyclus/session.py` | `_committed_through_samples`; stop-pad vanaf committed |
| `tests/test_incremental_transcription.py` | Worker: 14 s eerste job, failure cursor, stop-guards |
| `docs/superpowers/specs/2026-08-20-unprocessed-audio-tail-design.md` | Status accepted |

## Task order

1. Pure `commit_window` (TDD)
2. Incremental wiring + stop (TDD)
3. `processing_ratio` log
4. Verify pytest/ruff
5. Teamreview (niet in deze plan-file coderen)

---

### Task 1: Pure helper `commit_window`

**Owner:** `audio-speech`  
**Consult:** `core-python-architect`  
**Depends on:** none

**Files:**
- Modify: `chunk_transcription.py`
- Test: `tests/test_chunk_transcription.py`

**Produces:**

```python
UNPROCESSED_TAIL_SECONDS = 6.0

@dataclass(frozen=True)
class CommitWindow:
    slice_start: int
    commit_end: int

def commit_window(
    *,
    committed: int,
    cut_end: int,
    sample_rate: int,
    tail_seconds: float = UNPROCESSED_TAIL_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> CommitWindow: ...
```

**In scope:**
- [ ] Tests: 20 s eerste cut → 0 / 14 s; tweede committed=14 cut=40 → 12.5 / 34 s
- [ ] Tests: cuts 20/40/60/80 → commit_ends 14/34/54/74, starts 0/12.5/32.5/52.5
- [ ] Tests: `available == min_hold` → hold; `available < min_hold` → `commit_end = cut_end`
- [ ] Implementatie: `available = cut_end - committed`; `>=` voor hold

**Out of scope:** Whisper, jobs, UI

**Verification:** `pytest tests/test_chunk_transcription.py -q`

---

### Task 2: Cursors, job, stop-pad

**Owner:** `core-python-architect`  
**Consult:** `audio-speech`  
**Depends on:** Task 1

**Files:**
- Modify: `dicteercyclus/incremental.py`, `dicteercyclus/session.py`
- Test: `tests/test_incremental_transcription.py`

**In scope:**
- [ ] `_committed_through_samples` reset bij start/stop/cancel/te kort
- [ ] `_ChunkWhisperJob.commit_end_sample: int`
- [ ] Enqueue: venster via `commit_window`; cut schuift naar `cut_end`; committed niet
- [ ] Success + non-empty `raw`: dedupe, append, `committed = commit_end_sample` (ook als delta leeg)
- [ ] Exception of lege `raw`: committed ongewijzigd
- [ ] Stop: `committed == 0` → `[0, end]`; anders `[max(0, committed-overlap), end]`
- [ ] Test: 20 s feed → eerste wav ~14 s samples
- [ ] Test: Whisper-falen → committed blijft 0 of oude waarde
- [ ] Bestaande korte-chunk tests blijven no-hold (open ≪ 9 s)

**Out of scope:** live replace, bridge, overlap-setting

**Verification:** `pytest tests/test_incremental_transcription.py tests/test_live_paste.py tests/test_chunk_transcription.py -q`

---

### Task 3: processing_ratio log

**Owner:** `audio-speech`  
**Depends on:** Task 2

**Files:**
- Modify: `dicteercyclus/incremental.py`

**In scope:**
- [ ] Na Whisper: `chunk.whisper window=…s whisper=…s ratio=…` (geen transcripttekst)

**Verification:** unit via bestaande SequenceModel-job (optioneel caplog); ruff schoon

---

### Completion / AC mapping

| Spec AC | Task |
|---------|------|
| Geen `brandende... torts` (helper + venster) | 1–2 |
| `committed` niet bij falen | 2 |
| Stop-guards | 2 |
| Cursor-reeks 20/40/60/80 | 1 |
| `processing_ratio` zichtbaar | 3 |
| Live achterlopen | 2 (alleen confirmed emit) |
