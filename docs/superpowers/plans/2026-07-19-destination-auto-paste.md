# Destination auto-paste — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Per bestemming `auto_paste` (default uit): bij actieve bestemming
stuurt die flag klembord+plakken; zonder actieve geldt de globale setting.

**Architecture:** Pure helpers in `destinations.py`; session gebruikt
`resolve_auto_paste` i.p.v. alleen `self.auto_paste` bij deliver; dialoog
bewerkt de flag; i18n + help.

**Tech Stack:** Bestaande Python/tkinter/pytest/i18n.

**Spec:** `docs/superpowers/specs/2026-07-19-destination-auto-paste-design.md`

---

### Task 1: destinations helpers (TDD)

**Files:**
- Modify: `destinations.py`
- Modify: `tests/test_destinations.py`

- [ ] `sanitize_destinations` bewaart `auto_paste` bool (default `False`)
- [ ] `resolve_auto_paste(active, destinations, global_auto_paste) -> bool`
- [ ] Tests voor default, true/false, geen active → global
- [ ] Commit

### Task 2: Opnamesessie wiring

**Files:**
- Modify: `opnamesessie.py`
- Modify: `tests/test_opnamesessie.py`

- [ ] Na transcript: `effective = resolve_auto_paste(...)` met
      `get_destinations` + injecteerbare `get_active_destination` of
      `get_auto_paste: Callable[[], bool]`
- [ ] Klembord + paste alleen als effective True
- [ ] Test: active dest auto_paste false → geen copy/paste, wel save
- [ ] Commit

### Task 3: Dialoog + i18n + help

**Files:**
- Modify: `destinations_dialog.py`
- Modify: `locales/*.json`
- Modify: `docs/user/help.*.md`
- Modify: `CONTEXT.md` / `CHANGELOG.md` (kort)

- [ ] Checkbox in edit-subdialoog; kolom in tree
- [ ] Locale keys
- [ ] Help: globale vs per-bestemming
- [ ] Commit

### Task 4: Verify

- [ ] `pytest -q`
- [ ] Handmatige smoke: bestemming zonder paste → alleen bestand in map
