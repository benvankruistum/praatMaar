# Meeting Buddy tray- & agenda-UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Meeting Buddy gets a dedicated tray cascade, split agenda/properties dialogs, `.md` agenda library with Recents, quick-start, modules dialog that stays open after save, and mic window icons.

**Architecture:** Pure agenda I/O + recents in `meeting_buddy/agenda_store.py`; UI split into `agenda_dialog.py` + `properties_dialog.py`; `module.py` wires five `in_tray` actions (no `in_tray_root`); `tray.py` promotes per-module `in_tray` groups to root cascades; `modules_dialog.py` keeps open and rebuilds action buttons after apply.

**Tech Stack:** Python 3.10+, tkinter, pystray, pytest, existing `modules/settings_store.py`, i18n JSON locales.

**Spec:** `docs/superpowers/specs/2026-07-22-meeting-buddy-tray-ux-design.md`

## Global Constraints

- Branch: `feat/meeting-buddy-tray-ux` (never commit on `main`)
- Agenda files: UTF-8 `.md` only under `{app_dir}/meeting-buddy/agendas/`
- Display title = filename stem (optional `# Title` line may override display)
- No required title form field
- Loopback prefs stay in `meeting-buddy/config.json` via `save_meeting_buddy_preferences`
- TDD: failing test before production code
- Commit after each task; ruff-clean
- Dutch/English/German locale keys for all new UI strings

## File map

| File | Responsibility |
|------|----------------|
| `modules/_builtin/meeting_buddy/agenda_store.py` | List/load/save `.md`, display title, recents |
| `modules/_builtin/meeting_buddy/agenda_dialog.py` | Agenda UI (library + points + start/save) |
| `modules/_builtin/meeting_buddy/properties_dialog.py` | Loopback + output only |
| `modules/_builtin/meeting_buddy/prep_dialog.py` | Remove callers; delete or keep unused until Task 4 |
| `modules/_builtin/meeting_buddy/module.py` | Actions + start/quick/agenda/properties flows |
| `tray.py` | Root cascade per module with `in_tray` actions |
| `modules_dialog.py` | Stay open after save; refresh actions |
| `ui_icon.py` | Shared mic icon for Tk (`iconphoto`) |
| `locales/{nl,en,de}.json` | New strings |
| `docs/user/help.{nl,en,de}.md` | User-facing UX |
| `tests/test_meeting_buddy_agenda_store.py` | Store + recents |
| `tests/test_meeting_buddy_orchestrator.py` | Action flags / flows |
| `tests/test_tray_menu_modules.py` | Root cascade shape |

---

### Task 1: Agenda store (`.md` + recents)

**Files:**
- Create: `modules/_builtin/meeting_buddy/agenda_store.py`
- Test: `tests/test_meeting_buddy_agenda_store.py`

**Interfaces (produce):**
- `agendas_dir(app_dir: Path) -> Path`
- `display_title(path: Path, text: str | None = None) -> str`
- `parse_agenda_markdown(text: str) -> tuple[str | None, str]`
- `format_agenda_markdown(*, title: str | None, body: str) -> str`
- `list_agendas(app_dir: Path) -> list[Path]`
- `load_agenda(path: Path) -> tuple[str, str]`  # display_title, body
- `save_agenda(path: Path, body: str, *, title: str | None = None) -> Path`
- `default_new_path(app_dir: Path, body: str) -> Path`
- `list_recent(app_dir: Path, *, limit: int = 8) -> list[Path]`
- `touch_recent(app_dir: Path, path: Path, *, limit: int = 8) -> None`

Recents key in module `config.json`: `agenda_recents: list[str]` (absolute paths), via `load_config`/`save_config`.

- [ ] Write failing tests (stem title, H1 override, roundtrip, only `.md`, recent order, drop missing)
- [ ] Run `pytest tests/test_meeting_buddy_agenda_store.py -v` — FAIL
- [ ] Implement `agenda_store.py`
- [ ] Tests PASS
- [ ] Commit: `feat(meeting-buddy): add agenda markdown store and recents`

---

### Task 2: Properties dialog

**Files:**
- Create: `modules/_builtin/meeting_buddy/properties_dialog.py`
- Test: `tests/test_meeting_buddy_properties_dialog.py`

**Interfaces:**
- `@dataclass PropertiesResult: enable_loopback: bool; loopback_device: int | None`
- `show_properties_dialog(*, enable_loopback: bool, loopback_device: int | None, parent=None) -> PropertiesResult | None`

Move loopback UI from `prep_dialog.py`.

- [ ] Failing test for module/result contract
- [ ] Implement dialog
- [ ] PASS + commit: `feat(meeting-buddy): add properties dialog for loopback`

---

### Task 3: Agenda dialog (library UI)

**Files:**
- Create: `modules/_builtin/meeting_buddy/agenda_dialog.py`
- Test: `tests/test_meeting_buddy_agenda_dialog.py` (validation helpers)

**Interfaces:**
- `@dataclass AgendaDialogResult: agenda_text: str; path: Path | None; start: bool`
- `show_agenda_dialog(*, agenda_text: str, path: Path | None, app_dir: Path, mode: Literal["start","edit"], parent=None) -> AgendaDialogResult | None`

UI: Recent, All agendas, Open/Save/Save as/Open file (`.md`), body, topic count.
- `mode="start"`: Save, Start meeting, Cancel
- `mode="edit"`: Save, Close
- Reject Start when agenda empty; `touch_recent` on open/save/start

- [ ] TDD helpers + implement dialog
- [ ] Commit: `feat(meeting-buddy): add agenda dialog with library and recents`

---

### Task 4: Wire module actions + flows

**Files:**
- Modify: `modules/_builtin/meeting_buddy/module.py`
- Modify: `tests/test_meeting_buddy_orchestrator.py`
- Locales nl/en/de for new action/dialog keys
- Stop calling `show_meeting_prep_dialog`

**Actions (all `in_tray=True`, no `in_tray_root`):**
- `start_meeting`, `start_meeting_quick`, `stop_meeting`, `prepare_agenda`, `properties`

**Flows:**
- start → agenda dialog mode=start → set_agenda, touch_recent, `orchestrator.start()` with existing prefs
- quick → if empty agenda: open start dialog; else start immediately
- prepare → agenda dialog mode=edit
- properties → properties dialog → `save_meeting_buddy_preferences` + `reload_config`
- Keep `_agenda_path` on module

- [ ] Update orchestrator tests for tray action lists + monkeypatches
- [ ] Commit: `feat(meeting-buddy): wire cascade actions and split start flows`

---

### Task 5: Tray root cascade per module

**Files:**
- Modify: `tray.py`
- Test: `tests/test_tray_menu_modules.py`

**Menu order:** Settings, Destinations, per-module root cascades from `in_tray` actions, separator, Modules… (manage only), Help, Quit.

- [ ] TDD `context_menu_entries` shape with fake getters
- [ ] Implement
- [ ] Commit: `feat(tray): promote module tray actions to root cascades`

---

### Task 6: Modules dialog stay-open + window icon

**Files:**
- Modify: `modules_dialog.py`, `dictation.py`
- Create: `ui_icon.py`; refactor `tray._make_icon` to import from it
- Apply icon on modules/agenda/properties windows

**Stay-open:** `save()` calls `on_apply` then rebuilds action buttons via `get_enabled_module_ids: Callable[[], set[str]]` — do not destroy.

- [ ] Implement + tests where practical
- [ ] Commit: `feat(modules): keep modules dialog open after save; add window icon`

---

### Task 7: Docs + final sweep

**Files:** help.nl/en/de, modules-authoring if needed, locale gaps, spec status

- [ ] `pytest` on touched tests; `ruff check` + `ruff format`
- [ ] Commit: `docs: Meeting Buddy tray and agenda UX help`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Meeting Buddy ▸ at tray root | 4, 5 |
| No flat root Start/Stop | 4, 5 |
| Modules always stay open after save | 6 |
| Action buttons in modules dialog | 4, 6 |
| `.md` library + Open/Save as | 1, 3 |
| Title from filename | 1 |
| Recent above All | 1, 3 |
| Properties separate | 2, 4 |
| Start vs quick start | 4 |
| Mic icon | 6 |
| Locales/help | 4, 7 |
