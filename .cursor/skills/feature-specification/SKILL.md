---
name: feature-specification
description: Turn a praatMaar feature idea or user problem into a scoped product specification with goals, non-goals, requirements, acceptance criteria, risks, agent ownership, and required evidence. Use before implementing new or materially changed product behaviour.
---

# Feature specification (praatMaar)

Turn a feature idea or user problem into a **scoped product specification** before
implementation. Do **not** implement production code in this skill.

Prefer delegating analysis to the `product-owner` subagent when available; this
skill defines the required process and output even when you run it yourself.

## When to use

- New product behaviour
- Material change to dictation, Meeting Buddy, indicators, settings, privacy,
  packaging, or platform integration
- User says “feature”, “spec”, “requirements”, “acceptance criteria”, or asks
  what to build next for a problem

Do **not** use for pure refactors with no user-visible change, typo fixes, or
docs-only work (use `/update-documentation`).

## Inputs

From the user (ask one short question if missing 2+ of these):

1. The idea or symptom
2. Who hits the problem (if known)
3. Platforms in scope (default: current supported platforms in `docs/STATUS.md`)
4. Hard constraints (deadline, must stay local-first, etc.)

## Process

### 1. Orient

Run `/repository-orientation` first (or follow that skill inline). At minimum
read:

- `CONTEXT.md` — exact domain terms
- `AGENTS.md` — ownership matrix and default feature flow
- `docs/agents/shared-rules.md`
- `docs/STATUS.md`, relevant ADRs under `docs/adr/`
- Existing specs under `docs/superpowers/specs/` that overlap
- Affected code areas only enough to check docs↔implementation consistency

State conflicts between docs and code explicitly.

### 2. Restate the user problem

Use:

- **User:**
- **Situation:**
- **Problem:**
- **Impact:**
- **Desired outcome:**

Separate the underlying problem from any suggested technical solution.

### 3. Product fit

Recommend one of:

- proceed
- proceed with adjusted scope
- investigate first
- defer
- reject

Explain briefly. If reject / defer / investigate first, stop after a short
**Feature assessment** (template below) unless the user asks to continue.

If the change is cross-cutting or ownership/affected components are unclear, run
`/change-impact-analysis` before locking scope (or incorporate its findings into
Risks / Dependencies / Agent ownership).

### 4. Scope the smallest coherent slice

Define included behaviour and **explicit non-goals**. Prefer the smallest
coherent implementation that delivers meaningful value.

Apply product principles from `.cursor/agents/product-owner.md`:

- local-first by default
- unambiguous recording/processing states
- no unexpected focus steal
- recoverable failures
- no new settings without a meaningful user choice

### 5. Write the product specification

Fill every section in the template below. Requirements must be **observable**.

Avoid vague phrases such as “user-friendly”, “improve performance”, “native
enough”. Replace with testable expectations.

Number:

- functional requirements `FR-01`, `FR-02`, …
- quality requirements `QR-01`, `QR-02`, …

Acceptance criteria: Given/When/Then where practical.

### 6. Assign ownership

Using `AGENTS.md`:

- one **responsible** implementation agent
- consulting agents
- mandatory reviewers (`privacy-security`, `ux-product-design`, `quality-release`
  when relevant)
- required evidence for acceptance

Do not leave ownership as “the team” or “as discussed”.

### 7. Persist (when the user wants a durable artifact)

Default: present the spec in chat for approval.

When approved or when the user asks to save:

- Path: `docs/superpowers/specs/YYYY-MM-DD-<slug>-product.md`
- Status: `Draft` until the user accepts
- Feature branch only; never commit on `main`; commit only if the user asks

If an overlapping design already exists, link it and mark supersession or
relationship clearly.

### 8. Handoff (optional)

If implementation should start next, use `/agent-handoff` to produce
self-contained `# Assignment — [agent]` blocks (one per responsible agent).
Subagents may not see prior chat. The short template below is the minimum; prefer
the fuller `/agent-handoff` skill when delegating.

## Feature assessment template (fit-only / early exit)

```markdown
# Feature assessment

## Request
## User problem
## Product fit
## Recommendation
## Proposed scope
## Explicit non-goals
## Risks and dependencies
## Required agents
## Next decision
```

## Product specification template

```markdown
# Product specification — [name]

## Status
Draft | Review | Accepted | Implemented | Superseded

## Context
## Problem
## Goal
## Non-goals
## Users and scenarios

## Functional requirements
- FR-01 …
- FR-02 …

## Quality requirements
- QR-01 … (usability / accessibility / privacy / performance / reliability /
  platform / recovery / maintainability as relevant)

## Supported platforms
## Edge cases
## Privacy considerations
## Dependencies
## Risks

## Acceptance criteria
- Given … When … Then …

## Required evidence
## Agent ownership
## Open questions
```

## Agent handoff template

```markdown
# Assignment — [agent name]

## Background
## Objective
## In scope
## Out of scope
## Constraints
## Relevant repository areas
## Expected deliverable
## Acceptance criteria
## Required evidence
## Required reviewers
```

## Behavioural boundaries

- Do not implement substantial production code under this skill.
- Do not silently expand scope.
- Do not prescribe low-level implementation before the problem and scope are clear.
- Do not invent product facts when repository evidence is incomplete — list
  open questions instead.
- Do not assume Windows behaviour equals macOS or Linux.
- Flag any cloud or external processing explicitly.

## Done when

- Product fit recommendation is clear
- Spec (or assessment) is complete enough that an implementation agent can work
  without prior chat history
- Ownership and required evidence are assigned
- User knows the next decision (approve / adjust / investigate / defer)
- After acceptance: suggest `/implementation-plan` (then `/agent-handoff`)
