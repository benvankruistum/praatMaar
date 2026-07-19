---
name: prepare-release
description: >-
  Prepares a new praatMaar version: bumps pyproject version, cuts CHANGELOG,
  runs project /update-documentation and personal /code-review (Matt Pocock),
  then creates tag vX.Y.Z after user confirmation. Use for nieuwe versie,
  release, SemVer, or tag van praatMaar.
disable-model-invocation: true
---

# Prepare release (praatMaar)

Orchestrate a release on a **feature branch**, then optionally tag.

Always chain:

1. `/update-documentation` (branch-delta + full-audit — all surfaces:
   help, locales, docstrings, markdown)
2. `/code-review` (Matt Pocock — personal skill in `~/.cursor/skills/`)
3. Version bump + CHANGELOG cut
4. Tag **only** after explicit user OK

Details: [release-checklist.md](release-checklist.md).

## Hard rules

- Never commit/push on `main`. Branch: `release/vX.Y.Z`.
- Never create/push a tag until the user confirms version + tagging.
- No `--no-verify`, no force-push, no moving tags without asking.
- If `/update-documentation` (this repo) or `/code-review` (personal) is
  missing, stop and say so.

## Process

### 1. Orient

```bash
git status -sb
git fetch origin
git tag -l 'v*' --sort=-v:refname | head -10
grep '^version' pyproject.toml
```

Ask: target version (major/minor/patch or `X.Y.Z`), review base (default:
previous `v*` tag, else `origin/main`), full-audit docs (default yes).

### 2. Branch

```bash
git checkout main && git pull origin main
git checkout -b release/vX.Y.Z
```

### 3. `/update-documentation`

Run the **project** skill: delta vs `origin/main`, then full-audit.
Draft CHANGELOG notes for the cut in step 5.

### 4. `/code-review`

Fixed point = previous release tag, else `origin/main`.
Present findings; fix or get waiver before bump/tag.

### 5. Cut version

1. `pyproject.toml` → `version = "X.Y.Z"`
2. `CHANGELOG.md` — move `[Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD`; empty Unreleased
3. Sync example versions in `docs/release-windows.md` / `docs/release-macos.md` / STATUS if hardcoded
4. Commit when asked; push + `gh pr create`

### 6. Tag (after merge + user OK)

```bash
git checkout main && git pull origin main
git tag -a vX.Y.Z -m "praatMaar vX.Y.Z"
git push origin vX.Y.Z   # only with confirmation
```

Pushing `v*` triggers Windows Release Actions (`docs/release-windows.md`).
macOS `.app` remains manual (`docs/release-macos.md`).

### 7. Report

Version, tag status, PR URL, docs files, review blockers, CI next steps.
