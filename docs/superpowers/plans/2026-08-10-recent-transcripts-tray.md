# Recente transcripts tray — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tray/pill cascade “Recente transcripts” (max 5 datum/tijd-labels) die
geslaagde dicteer-transcripts opnieuw op het klembord zet.
**Spec:** [2026-08-10-recent-transcripts-tray-product.md](../specs/2026-08-10-recent-transcripts-tray-product.md)
**ADR:** n/a
**Architecture:** Pure listing in `recovery.py` (timestamp-`.txt` over default +
directory-bestemmingen); menu-model in `ui/tray.py` (disabled + submenu, refresh
bij `aboutToShow`); wiring/clipboard in `dictation.py`.
**Tech stack:** Python 3, PySide6 QMenu, pytest

## Global constraints

- Local-first; geen paste; geen nieuwe settings; geen focus-steal
- Geen commits op `main`; branch: `feat/recent-transcripts-tray`
- Geen app kill/restart tenzij de gebruiker dat vraagt
- Append-modus en Meeting Buddy buiten scope

## File map

| File | Role |
|------|------|
| `recovery.py` | `list_recent_transcripts`, label/format, read helper |
| `destinations.py` | `directory_save_paths` (alleen `file_mode=new`) |
| `ui/tray.py` | Cascade + disabled entries + menu refresh bij open |
| `tray.py` | Facade re-export indien nodig |
| `dictation.py` | Wiring: dirs → list → copy callbacks |
| `locales/{nl,en,de}.json` | Tray-strings |
| `tests/test_recovery.py` / nieuw | Listing/label tests |
| `tests/test_tray_menu_modules.py` | Menu-order + empty/cascade |
| `docs/user/help.{nl,en,de}.md` | Systeemvak-bullet |
| `CHANGELOG.md` / `docs/STATUS.md` | Unreleased + statusregel |

## Task order overview

1. Pure listing helpers (TDD)
2. Destination directory paths
3. Tray menu model + refresh
4. Dictation wiring + i18n
5. Docs / CHANGELOG / STATUS
6. pytest

---

### Task 1: Listing helpers

**Owner:** `core-python-architect`  
**Depends on:** none

**Files:**
- Modify: `recovery.py`
- Test: `tests/test_recovery.py` (of `tests/test_recent_transcripts.py`)

**In scope:**
- [x] `RECENT_TRANSCRIPT_LIMIT = 5`
- [x] Parse timestamp-stem `YYYY-MM-DD_HHMMSS` optional `_N`
- [x] `list_recent_transcripts(dirs, limit=5)` — mtime desc, skip bad dirs/non-matching
- [x] Label formatter per UI-taal + collision `#N`
- [x] `read_transcript_text(path)`

**Verification:**
- [x] `pytest tests/test_recent_transcripts.py tests/test_recovery.py -q`

**Completion criteria:** FR-02–FR-05, FR-07/08 helpers; AC 1/3/8 listing side

---

### Task 2: Destination directory paths

**Owner:** `core-python-architect`  
**Depends on:** none (parallel met 1)

**Files:**
- Modify: `destinations.py`
- Test: `tests/test_destinations.py` (of recent-tests)

**In scope:**
- [x] `directory_save_paths(destinations)` — unieke paths, skip append-mode

**Completion criteria:** FR-04, FR-09

---

### Task 3: Tray menu model

**Owner:** `core-python-architect`  
**Consult:** `ux-product-design`  
**Depends on:** Task 1 (entries shape)

**Files:**
- Modify: `ui/tray.py`
- Test: `tests/test_tray_menu_modules.py`

**In scope:**
- [x] Cascade na Bestemmingen
- [x] `disabled` entry type
- [x] `get_recent_transcript_entries` callback
- [x] Rebuild menu contents on `aboutToShow` (verse lijst)

**Completion criteria:** FR-01, FR-07, QR-05; AC 6

---

### Task 4: Dictation wiring + i18n

**Owner:** `core-python-architect`  
**Consult:** `privacy-security`  
**Depends on:** Task 1–3

**Files:**
- Modify: `dictation.py`, `locales/nl.json`, `locales/en.json`, `locales/de.json`

**In scope:**
- [x] Bouw entries uit default + `directory_save_paths(DESTINATIONS)`
- [x] Klik → `_copy_to_clipboard`; fout → print warn, geen crash
- [x] i18n keys: `tray.recent_transcripts`, `tray.recent_transcripts.empty`

**Completion criteria:** FR-06, FR-08, FR-11, QR-02/04; AC 2/7

---

### Task 5: User docs + changelog

**Owner:** `core-python-architect`  
**Depends on:** Task 4

**Files:**
- Modify: `docs/user/help.{nl,en,de}.md`, `CHANGELOG.md`, `docs/STATUS.md`

**In scope:**
- [x] Systeemvak-bullet over Recente transcripts
- [x] CHANGELOG Unreleased Added
- [x] STATUS: systeemvak-regel bijwerken

**Completion criteria:** Required evidence docs; AC help

---

### Task 6: Verification

**Owner:** `core-python-architect`  
**Review:** `quality-release` (later)

**Verification:**
- [x] `pytest` relevant suites green
- [ ] Handmatig (Windows): tray + pill → copy → plak in Kladblok

**Maps to:** alle AC’s
