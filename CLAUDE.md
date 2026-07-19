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

Issues en specs: markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`. Publieke issues: GitHub Issues.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/`. Zie `docs/agents/domain.md`.
