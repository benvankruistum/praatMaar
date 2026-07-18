# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets, transcribeert
lokaal met Faster-Whisper (geen cloud) en plakt de tekst in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Git-workflow

Altijd via feature-branches; **geen commits of pushes op `main`**.
Details: [CONTRIBUTING.md](CONTRIBUTING.md) · Cursor-rule: `.cursor/rules/git-branches.mdc`.

Lint/format: `ruff check` + `ruff format` (CI enforced). Zie CONTRIBUTING.

## Agent skills

Engineering skills (Matt Pocock e.d.) staan **persoonlijk** in `~/.cursor/skills/`
(niet in deze repo). Invoke met `/skill-name` (bijv. `/triage`, `/implement`).
Deze sectie is de per-repo wiring die die skills verwachten.

### Issue tracker

Issues en specs: markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`. Publieke issues: GitHub Issues.

### Triage labels

`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`
op de `Status:`-regel. Zie `docs/agents/triage-labels.md`.

### Domain docs

Single-context: één `CONTEXT.md` in de root plus `docs/adr/` voor beslissingen.
Zie `docs/agents/domain.md`.
