---
name: implementation-plan
description: Convert an approved praatMaar specification or ADR into small, ordered implementation slices with file scope, ownership, dependencies, tests, verification, and completion criteria.
---

# Implementation plan (praatMaar)

Turn an **approved** product specification and/or ADR into a sequenced plan of
small implementation slices. Each slice must be independently understandable,
testable, and assignable via `/agent-handoff`.

This skill writes a plan document. It does **not** implement the slices (unless
the user explicitly asks to execute the plan next).

## When to use

- Spec status is Accepted (or equivalent user approval)
- ADR is `Aanvaard` when the work depends on a new architectural choice
- Before multi-file or multi-agent implementation
- Before `executing-plans` / subagent-driven development

Do not invent a large plan from a vague idea — run `/feature-specification`
(and `/architecture-decision` if needed) first.

## Prerequisites

1. `/repository-orientation` for the topic (or a current brief).
2. Linked inputs:
   - product/design spec under `docs/superpowers/specs/` and/or
   - ADR under `docs/adr/`
3. Prefer `/change-impact-analysis` when ownership or blast radius is unclear.
4. Use exact terms from `CONTEXT.md` and owners from `AGENTS.md`.

If approval is missing, stop and say what must be accepted first.

## Plan goals

- **Small slices:** each task preferably one concern; avoid “boil the ocean”
- **Ordered:** dependencies explicit; later tasks can assume earlier completion
- **File-scoped:** create/modify/test paths named up front
- **Owned:** one responsible agent per task; consultants named
- **Verified:** tests or manual checks per task; overall acceptance mapped to
  spec FRs/ACs
- **Completable:** checkbox tasks with clear done criteria

## Output location

Default path:

`docs/superpowers/plans/YYYY-MM-DD-<slug>.md`

Match existing plan tone (see e.g. chunk-transcription plan): Goal, Architecture,
Tech stack, Global constraints, File map, numbered Tasks with checkboxes.

Feature branch only; commit only if the user asks; never on `main`.

## Plan template

```markdown
# [Title] Implementation Plan

> **For agentic workers:** Use `/agent-handoff` per task (or
> superpowers:subagent-driven-development / executing-plans). Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** …
**Spec:** [link]
**ADR:** [link or n/a]
**Architecture:** … (seams, modules, data flow — short)
**Tech stack:** …

## Global constraints
- …
- No commits on `main`; branch: `cursor/…` or `feat/…`
- Do not kill/restart the running app unless the user asks

## File map
| File | Role |
|------|------|

## Task order overview
1. …
2. …

---

### Task N: [short name]

**Owner:** `agent-name`  
**Consult:** …  
**Review:** …  
**Depends on:** Task … / none

**Files:**
- Create: …
- Modify: …
- Test: …

**In scope:**
- [ ] …

**Out of scope:**
- …

**Implementation notes:**
- Interfaces / contracts to preserve or add
- `host` / platform seam rules if relevant

**Verification:**
- [ ] Automated: `pytest …`
- [ ] Manual (if needed): …

**Completion criteria:**
- …
- Maps to FR-xx / AC-yy (from spec)

**Handoff:** produce with `/agent-handoff` before execution if running as subagent
```

## Process

### 1. Extract must-haves from the spec/ADR

List FR/AC items and architectural constraints. Mark deferred could-haves out of
this plan.

### 2. Derive the file map

Name real paths. Split generic core vs platform adapters (`AGENTS.md`). Do not
put WASAPI adapter work and Whisper semantics in the same task without a
boundary.

### 3. Slice vertically when possible

Prefer: pure helpers + tests → lifecycle wiring → UI/locales → platform glue →
docs → packaging. Adjust for the feature.

TDD: for pure logic, put failing tests in the same task or an immediately prior
task.

### 4. Assign ownership per task

One writer. Readonly agents (`ux-product-design`, `privacy-security`,
`quality-release`, `product-owner`) appear as consult/review, not as code owners.

### 5. Wire verification to acceptance

Every spec AC should map to at least one task’s verification or an explicit
final verification task for `quality-release`.

### 6. Add a final integration slice

Last tasks typically cover:

- end-to-end / smoke
- `/update-documentation` surfaces (help, locales, CHANGELOG, STATUS)
- packaging only if the change requires it
- handoff to `quality-release` + `product-owner` acceptance

### 7. Review the plan for anti-patterns

Reject or rewrite if you see:

- tasks without files or verification
- multiple implementers editing the same files without order
- “implement the rest of the feature” mega-tasks
- platform work leaking into generic modules
- missing privacy review when audio/transcripts/network are involved

## After the plan exists

Suggested next steps:

1. User approves the plan (Status informal: approved in chat is fine; note it).
2. `/agent-handoff` for Task 1 (or batch by owner).
3. Execute slices; check off boxes in the plan as tasks complete.
4. `quality-release` against the original spec ACs.

When the user asks to execute an existing plan file, prefer
superpowers `executing-plans` or `subagent-driven-development` and keep this
plan’s checkboxes as the source of progress.

## Behavioural boundaries

- Do not start coding under this skill unless the user asks to execute.
- Do not expand product scope beyond the approved spec/ADR; log temptations as
  follow-ups.
- Do not skip tests “to move faster” in the plan — put them in the slices.
- Do not assume one OS validates another.
- Keep Global constraints aligned with project rules (git branches, no surprise
  app restarts).

## Done when

- Plan file is written (or presented for approval) with ordered, owned, verified
  tasks
- File map covers the change
- Spec/ADR acceptance criteria are traceable to tasks
- Next execution step is clear (`/agent-handoff` or implement Task 1)
