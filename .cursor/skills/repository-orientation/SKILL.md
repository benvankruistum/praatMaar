---
name: repository-orientation
description: Orient an agent in the praatMaar repository before design, implementation, or review. Use when work requires understanding current architecture, terminology, existing decisions, relevant code, tests, or documentation.
---

# Repository orientation (praatMaar)

Build a grounded picture of the repo **before** design, implementation, or
review. Prefer evidence from the tree over assumptions from memory or prompts.

This skill is **read-only orientation**. Do not implement features here. Do not
invent missing product or architectural facts — mark them as unknown.

## When to use

- Start of a feature, bugfix, review, or investigation
- Before `/feature-specification`, implementation, or acceptance review
- When the agent (or subagent) lacks recent context for this checkout
- When docs and code may disagree

Skip only for trivial, already-scoped edits where the affected files are already
open and understood.

## Process

### 1. Git and workspace

```bash
git branch --show-current
git status -sb
git log -5 --oneline
```

Note: branch name, dirty state, whether you are on `main` (feature work must not
commit on `main` — see `.cursor/rules/git-branches.mdc`).

If the task is branch-scoped, also identify merge-base vs `origin/main` when
useful:

```bash
git fetch origin
git merge-base HEAD origin/main
git log --oneline $(git merge-base HEAD origin/main)..HEAD
```

### 2. Core product docs (always)

Read at least:

| Doc | Why |
|-----|-----|
| `README.md` | User-facing product summary |
| `CONTEXT.md` | **Mandatory** domain vocabulary — use exact terms |
| `AGENTS.md` | Ownership matrix and feature flow |
| `docs/STATUS.md` | What is shipped / in progress / deferred |
| `docs/agents/shared-rules.md` | Shared agent constraints |
| `docs/agents/domain.md` | How to consume CONTEXT + ADRs |

Follow `docs/agents/domain.md`: do not invent synonyms for glossary terms.

### 3. Decisions and prior designs (topic-scoped)

Search and open what touches the task:

- `docs/adr/*.md` — hard architectural decisions
- `docs/superpowers/specs/*` — feature designs / product specs
- `docs/superpowers/plans/*` — implementation plans when relevant
- `docs/HANDOFF*.md`, `docs/archive/HANDOFF*` — only if the topic matches
- `CHANGELOG.md` `[Unreleased]` / recent entries for recent behaviour changes

If an ADR conflicts with the intended change, **surface the conflict** before
proceeding.

### 4. Map the code seams

Locate the relevant areas (inspect before assuming paths still match):

| Concern | Typical locations |
|---------|-------------------|
| Entrypoint / tray / hotkeys | `dictation.py` |
| Dicteercyclus runtime | `opnamesessie.py` |
| Platform seam | `host/` (`Host` Protocol, `_win`, `_mac`, `_linux`) |
| Indicator (pill) | `indicator/` |
| Config / recovery | `config.py`, `recovery.py` |
| Modules / Meeting Buddy | `modules/`, `modules/_builtin/meeting_buddy/` |
| Audio / WASAPI | `modules/_builtin/audio_capture.py`, `wasapi_loopback.py`, speech modules |
| Settings UI | `ui/` |
| Packaging | `praatMaar.spec`, `installer/`, `packaging/` |
| Tests | `tests/` |

Use ripgrep / path search for the user's topic terms **and** CONTEXT terms
(e.g. `Opnamesessie`, `host`, `dicteercyclus`).

Ownership of who may change what: `AGENTS.md`.

### 5. Tests and verification hooks

Find existing tests for the area:

- `tests/test_*.py` matching the modules above
- CI expectations in `.github/workflows/` when review/release related
- Manual checklists in release docs if packaging/platform work

Note gaps: missing tests are findings, not permission to skip verification later.

### 6. Docs ↔ code consistency

For each important claim (seam, lifecycle, platform support, privacy):

- Confirm it still matches implementation
- Record **consistent** / **drift** / **unknown**

Never silently prefer the prompt over the repository.

### 7. Produce an orientation brief

Return a concise brief the next step can reuse (chat is enough; do not write a
repo file unless the user asks):

```markdown
# Orientation brief — [topic]

## Git
- Branch:
- Dirty:
- Relevant commits (if any):

## Domain terms in play
- (from CONTEXT.md — exact spellings)

## Existing decisions
- ADRs:
- Specs/plans:
- Conflicts:

## Relevant code
- Paths and one-line role each

## Tests / evidence hooks
-

## Docs vs code
- Consistent:
- Drift:
- Unknown:

## Likely owners (from AGENTS.md)
- Responsible:
- Consult:

## Safe next step
- e.g. `/feature-specification` | implement under [agent] | investigate X | stop
```

## Behavioural boundaries

- Read and search only; no feature implementation in this skill.
- Do not create ADRs, specs, or CONTEXT entries unless the user explicitly asks
  (point to `/feature-specification` or `/domain-modeling` instead).
- Do not treat Windows behaviour as proof for macOS/Linux.
- Do not assume local-only processing without checking dependencies and network
  use for the touched area.
- Keep the brief short; deep-dive only into files that affect the task.

## Done when

- Branch/workspace state is known
- CONTEXT terms for the topic are identified
- Relevant ADRs/specs are listed (or confirmed absent)
- Key code paths and tests are named
- Drift/unknowns are explicit
- A concrete next step is recommended
