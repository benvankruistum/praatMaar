# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets, transcribeert
lokaal met Faster-Whisper (geen cloud) en plakt de tekst in het actieve invoerveld.
Zie [dictation.py](dictation.py).

## Agent skills

### Issue tracker

Issues en specs worden lokaal opgeslagen als markdown onder `.scratch/<feature-slug>/`.
Zie `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: één `CONTEXT.md` in de root plus `docs/adr/` voor beslissingen.
Zie `docs/agents/domain.md`.
