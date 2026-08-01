# Shared agent rules — praatMaar

Every Cursor subagent in `.cursor/agents/` follows these rules in addition to
its own role prompt.

## Required orientation

Before making decisions or edits, follow the
[`/repository-orientation`](../../.cursor/skills/repository-orientation/SKILL.md)
skill (or the same steps inline):

1. Inspect the repository structure and current branch.
2. Read `README.md`, `CONTEXT.md`, `AGENTS.md`, and relevant files under `docs/`.
3. Search for applicable ADRs, designs, handoffs, status documents, tests, and
   earlier implementations.
4. Verify whether documentation and implementation agree.
5. Use the exact domain terminology defined in `CONTEXT.md`.
6. State assumptions and unresolved conflicts instead of silently inventing
   project facts.

Do not rely solely on the agent prompt. The repository is the current source of
truth.

## Collaboration

- Keep changes inside your assigned domain (see `AGENTS.md` ownership matrix).
- Do not overwrite another agent's active work.
- Do not make broad adjacent refactors unless they are necessary for the
  requested outcome.
- Preserve the `host` platform seam and other established architectural
  boundaries.
- Escalate cross-domain product decisions to `product-owner`.
- Escalate cross-cutting technical design to `core-python-architect`.
- For significant or difficult-to-reverse decisions, use
  `/architecture-decision` (ADR under `docs/adr/`) before large implementation.
- Every completed implementation must include suitable tests or other
  reproducible verification.
- Do not mark work complete merely because code compiles or a file was changed.
- Report changed files, verification performed, remaining risks, and required
  follow-up.

## Read-only agents

Agents marked `readonly: true` may inspect the repository, run tests and builds
for evidence, and produce reports. They must not edit production code, tests, or
packaging to “make verification pass”. Report precise fixes to the owning
implementation agent instead.
