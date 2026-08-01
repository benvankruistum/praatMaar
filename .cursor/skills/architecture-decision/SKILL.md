---
name: architecture-decision
description: Create or review an Architecture Decision Record for praatMaar. Use for significant, cross-cutting, expensive-to-reverse, security-sensitive, or platform-defining technical decisions.
---

# Architecture decision (praatMaar)

Create or review an **Architecture Decision Record (ADR)** under `docs/adr/`.
ADRs capture significant technical choices that should not be rediscovered or
silently overturned.

This skill writes or updates ADR markdown (and related `CONTEXT.md` term links
when needed). It does **not** implement the decided design in application code.

## When to use

Use an ADR when the decision is one or more of:

- cross-cutting (multiple modules / seams)
- expensive to reverse
- security- or privacy-sensitive
- platform-defining (Windows / macOS / Linux baseline, packaging model)
- establishes or changes a named architectural boundary

Prefer a feature spec under `docs/superpowers/specs/` for product behaviour that
does not lock architecture. Prefer `/feature-specification` for user outcomes;
use this skill for the technical choice underneath.

## Modes

| Mode | When |
|------|------|
| **create** | New decision; no ADR yet (default) |
| **review** | Validate, amend, supersede, or reject a draft/existing ADR |
| **amend** | Accepted ADR needs a dated addendum (same file) without changing the core decision |

Ask which mode only if ambiguous.

## Before writing

1. `/repository-orientation` on the decision topic.
2. Read existing `docs/adr/*.md` — avoid duplicates; link or supersede.
3. Read `CONTEXT.md` and `docs/agents/domain.md`.
4. Prefer `/change-impact-analysis` when blast radius is unclear.
5. Confirm product fit with `/feature-specification` or `product-owner` if the
   decision changes user-visible behaviour or privacy posture.

Owner for architectural ADRs: usually `core-python-architect`, with platform /
`audio-speech` / `privacy-security` consulting as needed (`AGENTS.md`).

## Status vocabulary

Match existing ADRs (Dutch labels preferred for consistency with 0001–0004):

| Status | Meaning |
|--------|---------|
| `Voorstel` | Draft under discussion |
| `Aanvaard` | Accepted; implement against this |
| `Vervangen` | Superseded by a later ADR (link it) |
| `Afgewezen` | Explicitly rejected (keep for history) |

Do not mark `Aanvaard` without stating who/what approved (user confirmation in
chat is enough; note it under Status or Gevolgen).

## File naming and numbering

- Path: `docs/adr/NNNN-short-kebab-slug.md`
- `NNNN` = next integer after the highest existing ADR (currently check
  `docs/adr/` — do not reuse numbers)
- Title line: `# NNNN — Short human title`
- Language: Dutch preferred for continuity; English acceptable if the decision
  is already discussed in English (see 0005) — stay consistent within one ADR

## ADR template (create)

Follow the structure of existing records (e.g. `0001-platform-seam.md`):

```markdown
# NNNN — [Title]

- **Status:** Voorstel | Aanvaard | Vervangen | Afgewezen
- **Datum:** YYYY-MM-DD
- **Context-term:** [exact term] — zie [CONTEXT.md](../../CONTEXT.md)
- **Feature-spec:** [link] (optional)
- **Supersedes / Superseded by:** [link] (optional)

## Context

Why a decision is needed now. Facts from the repo, not hypotheticals.

## Beslissing

What we will do. Concrete and testable. List interfaces, ownership boundaries,
and **Bewust buiten scope** when relevant.

## Alternatieven overwogen

- **Option A.** Why rejected / deferred.
- **Option B.** …

## Gevolgen

Positive and negative consequences: locality, leverage, complexity, platform
work, privacy, packaging, migration, testing.

## Verificatie

How we will know the decision holds (tests, smoke, PoC). Optional at Voorstel;
required before calling implementation complete.
```

Dated **Aanvulling (YYYY-MM-DD)** sections may extend an accepted ADR without
rewriting history.

## Process — create

1. State the decision question in one sentence.
2. Summarize constraints (local-first, `host` seams, supported platforms).
3. List options with trade-offs (at least one serious alternative).
4. Recommend a decision; mark Status `Voorstel` until the user accepts.
5. Write the ADR file on a feature branch (never commit on `main` unless asked).
6. If a new domain term is introduced, update `CONTEXT.md` in the same change
   set (or list it as required follow-up — do not leave orphan Context-term links).
7. Link related specs/plans; note required `/agent-handoff` owners for
   implementation.

## Process — review

Compare the ADR to the repository:

1. Is the Context still true?
2. Does Beslissing match current code, or is there drift?
3. Are Alternatieven fair (steelman, not strawman)?
4. Are Gevolgen (privacy, platform, packaging) complete?
5. Conflict with another ADR? Surface explicitly.
6. Recommendation: **keep** / **amend** / **supersede** / **reject** / **implement gap**

Output a short review before editing files.

## Process — amend / supersede

- **Amend:** add `## Aanvulling (YYYY-MM-DD)` to the existing ADR; do not erase
  the original Beslissing.
- **Supersede:** new ADR with Status path; set old ADR to `Vervangen` and link
  both ways.

## Behavioural boundaries

- Do not use an ADR to sneak in unrelated refactors.
- Do not accept cloud/external processing defaults without explicit product
  approval (`privacy-security` + `product-owner`).
- Do not scatter `sys.platform` as a “decision”; prefer named seams.
- Do not claim Linux support without a support matrix (`linux-platform`).
- Do not implement production code under this skill beyond ADR/`CONTEXT.md`
  documentation.

## Done when

**Create:** ADR file exists with Context, Beslissing, Alternatieven, Gevolgen;
status and next approval/implementation step are clear.

**Review:** decision (keep/amend/supersede/reject/gap) is explicit with evidence
from the repo.
