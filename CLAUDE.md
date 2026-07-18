# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets, transcribeert
lokaal met Faster-Whisper (geen cloud) en plakt de tekst in het actieve invoerveld.

**Gebruikersdocs:** [README.md](README.md) · status: [docs/STATUS.md](docs/STATUS.md)

## Agent skills

### Issue tracker

Issues en specs worden lokaal opgeslagen als markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`. Publieke issues: GitHub Issues.

### Domain docs

Single-context: één `CONTEXT.md` in de root plus `docs/adr/` voor beslissingen.
Zie `docs/agents/domain.md`.
