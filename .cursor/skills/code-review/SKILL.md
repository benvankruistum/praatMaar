---
name: code-review
description: Review praatMaar changes for correctness, architecture boundaries, platform isolation, lifecycle safety, focus behaviour, audio handling, privacy, tests, regressions, and documentation. Use before merging non-trivial code.
---

# Code review (praatMaar)

Review a diff before merge. Focus on **praatMaar-specific** risks: seams,
lifecycle, focus, audio, privacy, platforms, tests, and docs.

This skill is **read-only review** by default. Report findings; do not implement
fixes unless the user asks. Prefer evidence from the diff and repo over taste.

Project skill for this repo. It supersedes the personal Matt Pocock
`/code-review` **inside praatMaar** (same invoke name). For a pure
Standards+Spec two-axis review you may still open that personal skill
explicitly if needed; default here is the checklist below.

## When to use

- Before merging non-trivial PRs or feature branches
- After implementation slices complete
- When `/prepare-release` asks for review
- User says “review”, “code review”, or “before merge”

Skip only for trivial docs-only or one-line typo diffs with no behaviour change.

## Process

### 1. Pin the review range

Default fixed point: merge-base with `origin/main` (or `main`).

```bash
git fetch origin
git branch --show-current
git status -sb
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main)
git rev-parse "$BASE"
git log --oneline "$BASE"..HEAD
git diff --stat "$BASE"...HEAD
git diff "$BASE"...HEAD
```

If the user names a commit/tag/branch/PR base, use that instead. Empty diff →
stop and say so.

Also note uncommitted changes if the user wants “working tree” review.

### 2. Orient briefly

Read as needed:

- `CONTEXT.md` — domain terms
- `AGENTS.md` — ownership / seams
- Linked specs under `docs/superpowers/specs/` and ADRs under `docs/adr/`
  referenced by the branch
- `CONTRIBUTING.md` for git/lint expectations

If a product spec exists for the change, Spec compliance is in scope. If none,
say so and review against stated PR intent + repo invariants.

### 3. Review checklist

Inspect the diff against each applicable axis. Skip axes the diff does not
touch; state “n/a” rather than inventing issues.

#### Correctness

- Logic matches intended behaviour; edge cases (cancel, stop, failure) handled
- No swallowed exceptions without log or user-visible outcome
- Race/thread assumptions sound for GUI vs worker vs audio threads

#### Architecture boundaries

- Generic code does not import Win32/AppKit/`winreg`/WASAPI directly
- Changes respect `host` and indicator contracts
- No speculative abstractions unrelated to the change
- Ownership matches `AGENTS.md` (flag cross-domain edits without boundary)

#### Platform isolation

- `sys.platform` branches not scattered through generic modules
- Windows/macOS/Linux behaviour not assumed equivalent without note
- Packaging/spec/installer updates present when native deps change

#### Lifecycle safety

- `Opnamesessie` / dicteercyclus: start, stop, cancel, shutdown deterministic
- No leaked streams, threads, or temp files on failure paths
- Warm-up / model load does not block hotkey or UI thread inappropriately

#### Focus behaviour

- Indicators/overlays/dialogs do not steal focus from the dictation target
- No-activate / panel behaviour preserved where required
- Synthetic paste timing still waits for clipboard readiness
- State clarity issues → `/ux-state-review`

#### Audio handling

- Sample rate/channels/format conversions explicit
- No silent clipping, gaps, or unbounded retention of raw audio
- Adapter vs pipeline ownership respected (WASAPI adapter ≠ Whisper semantics)
- Device/model failures surfaced actionably

#### Privacy

- No new network/cloud path without explicit disclosure and product approval
- Transcripts/audio not logged by default
- Recovery/transcript retention bounded; deletion paths considered
- Escalate severe issues; run `/privacy-security-review` when the diff touches
  audio, transcripts, clipboard, logging, network, model download, permissions,
  installer, or new dependencies.

#### Tests and regressions

- Behaviour changes have tests or an explicit manual evidence gap
- Existing tests updated; no deleted coverage without reason
- Suggest commands: focused `pytest` paths from the diff

#### Documentation

- User-visible changes → help.nl/en/de + locales as needed
- CHANGELOG / STATUS when behaviour ships
- ADR/spec drift called out

#### Tooling already enforced

Do not nitpick what `ruff check` / `ruff format` already gate unless the diff
breaks them. Mention CI expectations if relevant.

### 4. Severity

| Level | Meaning |
|-------|---------|
| **Blocker** | Must fix before merge |
| **Should fix** | Real risk; fix in this PR if practical |
| **Nit** | Optional clarity/style within review scope |
| **Question** | Need author intent before judging |

### 5. Output format

```markdown
# Code review — [branch or range]

## Range
`$BASE...HEAD` (or working tree)

## Spec / ADR under review
[links or “none”]

## Summary
[2–4 sentences]

## Findings

### Blockers
- [file:area] …

### Should fix
- …

### Nits
- …

### Questions
- …

## Axis coverage
| Axis | Result |
|------|--------|
| Correctness | pass / issues / n/a |
| Architecture | … |
| Platform isolation | … |
| Lifecycle | … |
| Focus | … |
| Audio | … |
| Privacy | … |
| Tests | … |
| Docs | … |

## Suggested verification
- `pytest …`
- Manual checks …

## Merge recommendation
**Approve** | **Approve with follow-ups** | **Request changes** | **Insufficient evidence**
```

## Optional specialist consult

For large diffs, after your pass you may delegate (readonly):

- `/privacy-security-review` or `privacy-security` — data-flow / threat concerns
- `quality-release` — evidence gaps vs acceptance criteria
- `core-python-architect` — seam disputes

Do not duplicate their full reports unless consulted.

## Behavioural boundaries

- Do not rewrite the PR “while reviewing” unless asked to fix.
- Do not demand drive-by refactors outside the diff.
- Do not treat passing unit tests as proof of native/focus/audio correctness.
- Do not approve cloud or telemetry additions without product+privacy flags.
- Be specific: file, symbol, and why — not “needs cleanup”.

## Done when

- Range is clear and diff was inspected
- Applicable axes are covered
- Findings are severity-ranked
- Merge recommendation is explicit
