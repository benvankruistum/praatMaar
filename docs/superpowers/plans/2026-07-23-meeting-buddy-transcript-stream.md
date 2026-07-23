# Meeting Buddy live transcript stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream final Meeting Buddy transcript text into a growing `.md` file under `meeting-buddy/transcripts/` from start through stop, with a path notification on stop.

**Architecture:** Pure `TranscriptJournal` owns file I/O and markdown. `MeetingOrchestrator` creates it on start, appends final STT deltas, finalizes on stop. `MeetingBuddyModule.stop_meeting` shows the saved path via messagebox/console.

**Tech Stack:** Python 3.10+, pathlib, existing Meeting Buddy orchestrator/STT events, pytest, i18n JSON.

**Spec:** `docs/superpowers/specs/2026-07-22-meeting-buddy-transcript-stream-design.md`

## Global Constraints

- Branch: `feat/meeting-buddy-tray-ux` (continue here)
- Path: `{app_dir}/meeting-buddy/transcripts/YYYY-MM-DD_HHMM_<stem>.md`
- Append **only** `is_final=True` non-empty text; flush after each append
- No live in-process transcript API; no overlay transcript viewer
- Log path/errors without dumping full transcript text
- TDD; commit per task; ruff-clean; nl/en/de locales

## File map

| File | Role |
|------|------|
| `modules/_builtin/meeting_buddy/transcript_journal.py` | create / append / finalize |
| `modules/_builtin/meeting_buddy/orchestrator.py` | wire journal lifecycle |
| `modules/_builtin/meeting_buddy/module.py` | notify path on stop |
| `locales/{nl,en,de}.json` | saved message |
| `docs/user/help.{nl,en,de}.md` | one-line note |
| `tests/test_meeting_buddy_transcript_journal.py` | journal unit tests |
| `tests/test_meeting_buddy_orchestrator.py` | start/append/stop integration |

---

### Task 1: TranscriptJournal (pure I/O)

**Files:**
- Create: `modules/_builtin/meeting_buddy/transcript_journal.py`
- Test: `tests/test_meeting_buddy_transcript_journal.py`

**Interfaces:**
```python
def transcripts_dir(app_dir: Path) -> Path: ...

def safe_stem(title: str) -> str: ...  # filesystem-safe; default "meeting"

@dataclass
class TranscriptJournal:
    path: Path
    @classmethod
    def create(cls, app_dir: Path, *, title: str, agenda_titles: list[str], started_at: datetime | None = None) -> TranscriptJournal: ...
    def append_final(self, text: str) -> None: ...  # no-op if blank; space-separate chunks
    def finalize(self, *, topics: Sequence[Topic] | None, ended_at: datetime | None = None) -> Path: ...
```

Markdown start = title H1, Gestart, Status: lopend, ## Agenda checkboxes unchecked, ## Transcript blank line.

Finalize: Status → gestopt, add Gestopt line, rewrite Agenda section from topics (`[x]` if DISCUSSED).

- [ ] Failing tests: dir path, create content, append finals, ignore empty, finalize checkboxes
- [ ] Implement + PASS
- [ ] Commit: `feat(meeting-buddy): add streaming transcript journal`

---

### Task 2: Wire orchestrator

**Files:**
- Modify: `orchestrator.py`
- Modify: `tests/test_meeting_buddy_orchestrator.py` (or new focused test)

On `start`: after agenda applied to state, `TranscriptJournal.create` with title from agenda path stem if available else first topic / `"Meeting"`, agenda titles from `parse_agenda`. Store `_journal`.

On `on_stt_event` final delta: `_journal.append_final(delta.text)` inside try/except log.

On `stop`: before clear, `_journal.finalize(topics=state.topics)`; expose `last_transcript_path: Path | None` property for module.

Module may pass agenda title via `set_agenda` + optional `set_agenda_path` / title string — use orchestrator `_agenda_text` + `parse_agenda` for titles; title display = first line stem helper or `"Meeting"`.

If module has `_agenda_path`, pass `title=display_title(path)` into start — add optional `journal_title: str | None` on start or set before start from module `_begin_meeting`.

Simplest: `orchestrator.start` uses:
```python
titles = parse_agenda(self._agenda_text)
title = self._journal_title or (titles[0] if titles else "Meeting")
```
Module sets `_orchestrator.set_journal_title(...)` from agenda path stem before start.

- [ ] Tests with tmp_path + fake STT finals assert file grows
- [ ] Commit: `feat(meeting-buddy): stream finals into transcript journal`

---

### Task 3: Stop notification + docs/locales

**Files:**
- Modify: `module.py` `stop_meeting`
- Locales: `modules.meeting_buddy.transcript.saved` with `{path}`
- Help nl/en/de: note that transcripts land under Meeting Buddy transcripts folder
- Spec status → Geïmplementeerd

```python
path = orchestrator.stop_and_transcript_path()  # or stop(); path = orchestrator.last_transcript_path
# print + messagebox.showinfo
```

- [ ] Commit: `feat(meeting-buddy): notify when meeting transcript is saved`

---

## Spec coverage

| Spec | Task |
|------|------|
| transcripts dir + .md create on start | 1, 2 |
| append finals during session | 1, 2 |
| finalize header/agenda on stop | 1, 2 |
| message with path | 3 |
| no live API / no overlay transcript | (by omission) |
| help/locales | 3 |
