# praatMaar

Lokale Windows-dicteertool (UI/spraak: nl/en/de). Neemt spraak op via een
sneltoets, transcribeert lokaal met Faster-Whisper (geen cloud) en plakt de tekst
in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Git-workflow

Altijd via feature-branches; **geen commits of pushes op `main`**.
Details: [CONTRIBUTING.md](CONTRIBUTING.md) · Cursor-rule: `.cursor/rules/git-branches.mdc`.

Lint/format: `ruff check` + `ruff format` (CI enforced). Zie CONTRIBUTING.

## Cursor subagents

Specialist agents in `.cursor/agents/` (aanroepen met `/naam`).
Index + ownership: [AGENTS.md](AGENTS.md) · shared rules:
[docs/agents/shared-rules.md](docs/agents/shared-rules.md).

## Agent skills

### Project skills

In `.cursor/skills/` (deze repo):

| Skill | Wanneer |
|-------|---------|
| `/update-documentation` | Docs sinds branch / full-audit: help, locales, docstrings, markdown |
| `/prepare-release` | Nieuwe versie: docs + `/code-review` + tag (na bevestiging) |
| `/feature-specification` | Feature-idee → product-spec (scope, AC, ownership) vóór implementatie |
| `/repository-orientation` | Repo/architectuur/terminologie begrijpen vóór design, build of review |
| `/agent-handoff` | Zelfstandige opdracht voor een subagent zonder chat-context |
| `/change-impact-analysis` | Blast radius vóór cross-cutting change (owners, privacy, tests, docs) |
| `/architecture-decision` | ADR maken of reviewen (seams, privacy, platform, lastig terug te draaien) |
| `/implementation-plan` | Goedgekeurde spec/ADR → geordende implementatieslices met tests/owners |
| `/code-review` | Review vóór merge (seams, lifecycle, focus, audio, privacy, tests, docs) |
| `/whisper-evaluation` | Faster-Whisper meten (fixtures: accuracy, latency, CPU/RAM, VAD, model) |
| `/release-readiness` | Go/no-go vóór tag (tests, builds, installer, changelog, privacy, limits) |
| `/privacy-security-review` | Privacy/security van een change (audio, logs, netwerk, deps, installer) |
| `/ux-state-review` | Interaction states (idle→error), focus, keyboard, a11y, platform |

### Issue tracker

Agent-skills: markdown onder `.scratch/<feature-slug>/` (lokaal).
Zie `docs/agents/issue-tracker.md`. Publieke meldingen: GitHub Issues.

### Triage labels

Vijf canonieke triage-rollen (default strings, ongewijzigd).
Zie `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/`. Zie `docs/agents/domain.md`.

### Matt Pocock engineering skills (globaal)

In `~/.cursor/skills/` — o.a. `/domain-modeling`, `/grill-with-docs`,
`/wayfinder`, `/to-spec`, `/tdd`. Vereisen bovenstaande `docs/agents/*`-layout.
