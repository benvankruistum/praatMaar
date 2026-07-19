---
name: update-documentation
description: >-
  Updates all praatMaar documentation surfaces: markdown docs, user help
  (nl/en/de), UI locale strings, module/class/Protocol docstrings and inline
  API docs. Discovers what is new since the current branch vs main, or runs a
  full app documentation audit. Use when documenting praatMaar, docs sinds
  branch, help-bestanden, docstrings, of volledige documentatie-rondgang.
disable-model-invocation: true
---

# Update documentation (praatMaar)

Project skill for this repo only. **Every documentation surface in scope must
be considered** — not only README/STATUS. If the delta touches behaviour or
APIs, update the matching help, locales, and inline docs in the same pass.

## Modes

| Mode | When |
|------|------|
| **branch-delta** | Document what changed on the current branch vs `main` |
| **full-audit** | Walk the whole app and fill gaps on every surface below |

Default: **branch-delta**. For “overal / compleet / volledige app” or when
`/prepare-release` asks: also run **full-audit**.

## Doc map (complete — do not skip a row)

| Surface | Paths / what to update |
|---------|------------------------|
| User README | `README.md` |
| In-app help | `docs/user/help.nl.md`, `help.en.md`, `help.de.md` — **always keep the three languages in sync** |
| UI copy | `locales/nl.json`, `en.json`, `de.json` (tray tooltips, settings, splash, help dialog, state labels) |
| Status | `docs/STATUS.md` |
| Changelog | `CHANGELOG.md` (`[Unreleased]`, Keep a Changelog + SemVer) |
| Domain | `CONTEXT.md`, `docs/adr/*.md` |
| Agent wiring | `docs/agents/*`, `CLAUDE.md`, `.cursor/skills/README.md` |
| Release / TCC | `docs/release-windows.md`, `docs/release-macos.md`, `docs/macos-permissions.md` |
| Contributor / security | `CONTRIBUTING.md`, `SECURITY.md` when workflow or reporting changes |
| **Module docstrings** | Top-of-file `"""…"""` on changed modules (`dictation.py`, `opnamesessie.py`, `host/`, `indicator/`, `tray.py`, `settings*.py`, `hotkeys.py`, `mac_input.py`, `destinations*.py`, …) |
| **Interface / API docs** | `Protocol`s (e.g. `host.Host`), public classes/functions: method docstrings, parameter/return meaning, platform notes |
| **Inline comments** | Only where they document non-obvious contracts (seam boundaries, TCC, thread/runloop rules) — no narrating obvious code |

Read `CONTEXT.md` before naming domain terms. Follow `docs/agents/domain.md`.
Match existing Dutch docstring tone (see `host/__init__.py`, `opnamesessie.py`).

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

### 2. Inventory (per surface)

From the diff, tick what needs updates:

- [ ] User-visible behaviour → help.*.md + locales + README/STATUS as needed
- [ ] New/changed settings or tray items → `locales/*.json` (+ help if explanatory)
- [ ] Public API / Protocol / injectables → interface docstrings
- [ ] Module responsibility shift → module docstring
- [ ] Architecture / seam decision → CONTEXT and/or ADR
- [ ] Platform/TCC/build → release + macos-permissions docs
- [ ] Changelog-worthy → `CHANGELOG.md` `[Unreleased]`

### 3. Write (order)

Apply only what the inventory requires, but **do not leave a surface stale**
when another surface was updated for the same change:

1. Inline: module docstring → class/Protocol → public methods
2. `locales/*.json` (nl + en + de together)
3. `docs/user/help.nl.md` then mirror to `.en` / `.de`
4. `CHANGELOG.md` `[Unreleased]`
5. `docs/STATUS.md` (date + support/werkt/roadmap)
6. `README.md` if install/start/platform changed
7. `CONTEXT.md` / `docs/adr/` if terms or decisions changed
8. Release/TCC / CONTRIBUTING / SECURITY if those areas changed
9. `CLAUDE.md` / agent docs if agent workflow changed

Style: concise; Dutch for user-facing and most module docs; keep en/de help
and locale files idiomatic, not machine-calqued.

### 4. Consistency check

Before finishing:

- Help nl/en/de describe the same features
- Locale keys used in code exist in all three locale files
- Docstrings use CONTEXT glossary terms
- No contradictory claims between STATUS, README, and help

### 5. Report

Base ref, surfaces touched, files touched, leftover gaps (offer full-audit).

## Process — full-audit

### 1. Map the app

Entrypoints and packages: `dictation.py`, `opnamesessie.py`, `host/`,
`indicator/`, `tray.py`, `settings.py`, `settings_process.py`, `hotkeys.py`,
`mac_input.py`, `destinations*.py`, `i18n.py`, `locales/`, packaging,
`.github/workflows/`. Cross-check `CONTEXT.md` and `docs/STATUS.md`.

### 2. Gap checklist (all surfaces)

For each row: **documented / stale / missing**

- [ ] Install & start (Windows + macOS) — README
- [ ] TCC / permissions — `docs/macos-permissions.md` + help if user-facing
- [ ] Dicteercyclus & hotkeys — help + locales + relevant docstrings
- [ ] Settings & tray (bestemmingen, help) — locales + help + settings module docs
- [ ] Recovery, logging paths, i18n
- [ ] Platform differences (warm mic, indicator, settings subprocess) — STATUS + module docs
- [ ] `Host` Protocol and adapters — interface docstrings complete
- [ ] Indicator contract (`RecordingState`, notify/push) — `_contract` docs
- [ ] Build & release (Win + Mac)
- [ ] Agent/domain docs + project skills README
- [ ] CHANGELOG `[Unreleased]` reflects shipped-but-untagged work

### 3. Fill gaps

Prioritise: (1) help + locales, (2) STATUS/README, (3) public API docstrings,
(4) ADRs/CONTEXT. Do not invent features.

## Anti-patterns

- Updating CHANGELOG/STATUS but leaving help or locales stale for the same feature
- Updating only `help.nl.md` without en/de
- Adding locale keys in one language only
- Essay-length duplication across README / STATUS / help — link instead
- Noise comments that restate the code
- Version tags → `/prepare-release`
