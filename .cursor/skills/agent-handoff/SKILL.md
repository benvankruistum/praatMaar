---
name: agent-handoff
description: Create a self-contained implementation, research, design, or review assignment for a praatMaar subagent. Use when delegating work to another agent that will not automatically receive the current conversation context.
---

# Agent handoff (praatMaar)

Produce a **self-contained assignment** for a specialist subagent. Assume the
target agent receives **no** prior chat history — only this handoff plus the
repository.

Do not implement the work in this skill unless the user explicitly asks you to
both write the handoff and execute it.

## When to use

- Delegating to `.cursor/agents/*` (`product-owner`, `core-python-architect`,
  `audio-speech`, `windows-platform`, `macos-platform`, `linux-platform`,
  `ux-product-design`, `privacy-security`, `quality-release`)
- Splitting a feature across multiple owners
- Resuming work in a new chat / Cloud Agent / Automation
- After `/feature-specification` when implementation or review should start

## Before writing

1. Prefer a fresh `/repository-orientation` brief for the topic (or reuse one
   from this conversation if still accurate).
2. Confirm ownership in `AGENTS.md` — one **responsible** agent; name consultants
   and reviewers explicitly.
3. If product scope is unclear, run `/feature-specification` (or ask
   `product-owner`) before an implementation handoff.
4. Use exact terms from `CONTEXT.md`.

## Handoff rules

- **Self-contained:** include background, objective, scope, constraints, paths,
  acceptance criteria, and evidence — no “as discussed above”.
- **Observable outcomes:** what done looks like, not vague intent.
- **Bounded:** explicit out-of-scope; no silent scope expansion.
- **One owner:** do not assign overlapping write ownership to two agents for the
  same files without stating who may edit what.
- **Readonly respect:** for `readonly: true` agents, ask for reports/reviews/specs,
  not production code edits.
- **Seams:** remind implementers to keep native code behind `host` / platform
  adapters; see `docs/agents/shared-rules.md`.

## Process

### 1. Choose the target agent and assignment type

| Type | Typical agent | Deliverable |
|------|---------------|-------------|
| Implementation | `core-python-architect`, `audio-speech`, platform | Code + tests + report |
| Research / PoC | `linux-platform`, `audio-speech`, … | Findings + recommendation (+ ADR if needed) |
| Design | `ux-product-design`, `product-owner` | Spec / flows / AC |
| Review | `privacy-security`, `quality-release`, `product-owner` | Decision + findings |

### 2. Fill the assignment template

Copy every section. Mark unknowns as open questions rather than inventing facts.

### 3. Attach pointers (not dumps)

Link concrete paths, ADRs, and specs. Quote only the minimum critical excerpts
(e.g. a single FR or constraint). Do not paste entire specs when a path suffices.

### 4. Define handoff conditions

State when the assignee should stop and return:

- acceptance criteria met with evidence, or
- blocked (list blocker + what is needed), or
- recommendation only (research/design/review types)

### 5. Deliver

Present the assignment in chat. Optionally save under
`.scratch/<feature-slug>/handoff-<agent>.md` if the user wants a durable local
artifact (see `docs/agents/issue-tracker.md`). Commit only if asked; never on
`main`.

When the user wants execution next, invoke the named subagent with the full
assignment text as the task prompt.

## Assignment template

```markdown
# Assignment — [agent name]

## Type
Implementation | Research | Design | Review

## Background
Why this work exists. User problem in plain language. Link related specs/ADRs.

## Objective
Single primary outcome.

## In scope
- …

## Out of scope
- …

## Constraints
- Product / privacy / platform / performance / compatibility
- Must follow `CONTEXT.md` terminology and `host` seams

## Relevant repository areas
- Paths (files/dirs) and why they matter
- Related tests

## Domain terms
- Exact terms from CONTEXT.md used in this work

## Expected deliverable
What to return (report format, code areas, ADR, UX spec, etc.)

## Acceptance criteria
- Given / When / Then (or checklist the agent can verify)

## Required evidence
- Tests to run, manual checks, screenshots, measurements, …

## Required reviewers
- Agents that must review before calling the work done

## Consulting agents
- Who to consult; what question to ask them

## Stop conditions
- Done / blocked / needs product decision — when to return

## Open questions
- …
```

## Multi-agent packages

When several agents must work in sequence, produce **one assignment per agent**
and a short ordering note:

```markdown
# Handoff package — [feature]

## Order
1. [agent] — …
2. [agent] — …

## Shared context
- Spec path:
- Non-goals:
- Global constraints:
```

Do not merge multiple write-assignments into one prompt.

## Behavioural boundaries

- Do not leave critical context only in conversation memory.
- Do not prescribe low-level implementation detail that belongs to the
  specialist unless it is a hard product constraint.
- Do not mark the assignee’s work accepted from this skill alone — acceptance
  stays with `product-owner` / `quality-release` as appropriate.
- Do not invent ownership that contradicts `AGENTS.md` without calling out the
  exception and why.

## Done when

- A named agent could execute without reading this chat
- Scope, non-goals, AC, evidence, and reviewers are explicit
- Ownership matches `AGENTS.md` (or an explained exception)
- Next action is clear: invoke agent / wait for approval / save artifact
