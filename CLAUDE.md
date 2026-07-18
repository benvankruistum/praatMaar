# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets, transcribeert
lokaal met Faster-Whisper (geen cloud) en plakt de tekst in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Git-workflow

Altijd via feature-branches; **geen commits of pushes op `main`**.
Details: [CONTRIBUTING.md](CONTRIBUTING.md) · Cursor-rule: `.cursor/rules/git-branches.mdc`.

Lint/format: `ruff check` + `ruff format` (CI enforced). Zie CONTRIBUTING.

## Agent skills

### Issue tracker

Issues en specs worden lokaal opgeslagen als markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`. Publieke issues: GitHub Issues.

### Domain docs

Single-context: één `CONTEXT.md` in de root plus `docs/adr/` voor beslissingen.
Zie `docs/agents/domain.md`.
