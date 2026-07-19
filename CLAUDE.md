# praatMaar

Lokale Windows-dicteertool (UI/spraak: nl/en/de). Neemt spraak op via een
sneltoets, transcribeert lokaal met Faster-Whisper (geen cloud) en plakt de tekst
in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Git-workflow

Altijd via feature-branches; **geen commits of pushes op `main`**.
Details: [CONTRIBUTING.md](CONTRIBUTING.md) · Cursor-rule: `.cursor/rules/git-branches.mdc`.

Lint/format: `ruff check` + `ruff format` (CI enforced). Zie CONTRIBUTING.

## Agent skills

### Project skills

In `.cursor/skills/` (deze repo):

| Skill | Wanneer |
|-------|---------|
| `/update-documentation` | Docs sinds branch / full-audit: help, locales, docstrings, markdown |
| `/prepare-release` | Nieuwe versie: docs + `/code-review` + tag (na bevestiging) |

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
