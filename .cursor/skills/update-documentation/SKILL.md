---
name: update-documentation
description: >-
  Updates praatMaar documentation from branch changes and/or a full app
  walkthrough. Discovers what is new since the current branch vs main, writes or
  refreshes README, STATUS, CHANGELOG, user help, ADRs, and CONTEXT. Use when
  documenting praatMaar, docs sinds branch, or volledige documentatie-rondgang.
disable-model-invocation: true
---

# Update documentation (praatMaar)

Project skill for this repo only. Two modes (ask if unclear):

| Mode | When |
|------|------|
| **branch-delta** | Document what changed on the current branch vs `main` |
| **full-audit** | Walk the whole app and fill documentation gaps |

Default: **branch-delta**. For “overal / compleet / volledige app” or when
`/prepare-release` asks: also run **full-audit**.

## Doc map

| Kind | Paths |
|------|--------|
| User-facing | `README.md`, `docs/user/help.nl.md` (+ `.en` / `.de`) |
| Status | `docs/STATUS.md` |
| Changelog | `CHANGELOG.md` (Keep a Changelog + SemVer) |
| Domain | `CONTEXT.md`, `docs/adr/` |
| Agent wiring | `docs/agents/`, `CLAUDE.md` |
| Release | `docs/release-windows.md`, `docs/release-macos.md`, `docs/macos-permissions.md` |

Read `CONTEXT.md` before naming domain terms. Follow `docs/agents/domain.md`.

## Git

- Feature branch only; never commit on `main`.
- Commit/push only when the user asks.

## Process — branch-delta

### 1. Diff vs main

```bash
git fetch origin
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main)
git log --oneline "$BASE"..HEAD
git diff --stat "$BASE"...HEAD
git diff "$BASE"...HEAD
```

Empty diff → say so; offer full-audit or stop.

### 2. Inventory

From the diff: user-visible behaviour, platform/TCC, architecture (ADR?),
STATUS matrix, changelog gaps.

### 3. Write

Only what the delta needs:

1. `CHANGELOG.md` → `[Unreleased]` (Added/Changed/Fixed/Removed)
2. `docs/STATUS.md` — support table, werkt-lijst, roadmap; “Laatst bijgewerkt”
3. `README.md` — install/start/platform
4. `docs/user/help.*.md` — keep nl/en/de in sync
5. `CONTEXT.md` / `docs/adr/` — terms & decisions
6. Release/TCC docs — only if build or permissions changed

Concise Dutch for user docs; match neighbouring tone.

### 4. Report

Base ref, files touched, leftover gaps.

## Process — full-audit

### 1. Map the app

Entrypoints: `dictation.py`, `opnamesessie.py`, `host/`, `indicator/`,
`tray.py`, `settings.py`, `settings_process.py`, `hotkeys.py`, `mac_input.py`,
`destinations*.py`, packaging, `.github/workflows/`. Cross-check `CONTEXT.md`
and `docs/STATUS.md`.

### 2. Gap checklist

Documented / stale / missing:

- [ ] Install & start (Windows + macOS)
- [ ] TCC / permissions (`docs/macos-permissions.md`)
- [ ] Dicteercyclus & hotkeys
- [ ] Settings & tray (bestemmingen, help)
- [ ] Recovery, logging paths, i18n
- [ ] Platform differences (warm mic, indicator, settings subprocess)
- [ ] Build & release (Win + Mac)
- [ ] Agent/domain docs accurate?

### 3. Fill gaps

Prioritise user-facing + STATUS. Propose ADRs for undocumented decisions.
Do not invent features.

## Anti-patterns

- No duplicate essays across README / STATUS / help — link instead.
- No version tags here → `/prepare-release`.
