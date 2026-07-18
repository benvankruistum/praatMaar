# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets, transcribeert
lokaal met Faster-Whisper (geen cloud) en plakt de tekst in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Git-workflow

Altijd via feature-branches; **geen commits of pushes op `main`**.
Details: [CONTRIBUTING.md](CONTRIBUTING.md) · Cursor-rule: `.cursor/rules/git-branches.mdc`.

Lint/format: `ruff check` + `ruff format` (CI enforced). Zie CONTRIBUTING.

## Agent skills

Project skills (Matt Pocock engineering set) staan in `.cursor/skills/`.
Invoke met `/skill-name` (bijv. `/triage`, `/implement`). Bron:
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT).

| Skill | Wanneer |
|-------|------|
| `grill-with-docs` | Plan/design scherpstellen + ADRs/glossary |
| `triage` | Issues door triage-staten bewegen |
| `to-spec` | Spec/PRD schrijven |
| `to-tickets` | Spec → implementatietickets |
| `implement` | Ticket uitvoeren |
| `prototype` | Snelle spike/prototype |
| `tdd` | Test-driven implementatie |
| `code-review` | Code review |
| `improve-codebase-architecture` | Architectuur verbeteren |
| `domain-modeling` | Glossary + ADRs |
| `diagnosing-bugs` | Bugs systematisch debuggen |
| `wayfinder` | Onzekerheid verkennen via tickets |
| `codebase-design` | Codebase-ontwerp |
| `research` | Onderzoeksvragen |
| `ask-matt` | Advies in Matt Pocock-stijl |
| `setup-matt-pocock-skills` | Repo-config voor deze skills herzien |

### Issue tracker

Issues en specs: markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`. Publieke issues: GitHub Issues.

### Triage labels

`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`
op de `Status:`-regel. Zie `docs/agents/triage-labels.md`.

### Domain docs

Single-context: één `CONTEXT.md` in de root plus `docs/adr/` voor beslissingen.
Zie `docs/agents/domain.md`.
