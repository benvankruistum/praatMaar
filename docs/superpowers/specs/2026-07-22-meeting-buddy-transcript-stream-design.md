# Design — Meeting Buddy live transcript op schijf

- **Datum:** 2026-07-22
- **Status:** Review (wacht op goedkeuring)
- **Branch:** `feat/meeting-buddy-tray-ux` (of opvolger `feat/meeting-buddy-transcript-stream`)
- **Gerelateerd:**
  [2026-07-19-meeting-buddy-mvp-design.md](2026-07-19-meeting-buddy-mvp-design.md),
  [2026-07-22-meeting-buddy-tray-ux-design.md](2026-07-22-meeting-buddy-tray-ux-design.md)

## Probleem

Meeting Buddy transcribeert wel tijdens een sessie (voor hints), maar bewaart
geen bruikbaar transcript. Voor latere LLM-beoordeling moet de beschikbare tekst
**tijdens** de meeting al op schijf staan en meegroeien.

## Doel

Bij elke meeting een Markdown-bestand in de Meeting Buddy-datamap dat vanaf
start bestaat, met final transcript-tekst die incrementeel wordt geappend, zodat
externe tools (later: LLM) het bestand kunnen meelezen. Bij stop: header
afronden + korte melding met pad.

## Beslissingen

| Onderwerp | Keuze |
|-----------|--------|
| Locatie | `%APPDATA%\praatMaar\meeting-buddy\transcripts\` (eigen map, niet dicteer-transcripts) |
| Formaat | Eén `.md` met kop + `## Transcript` |
| Schrijfmodel | Continu append van **final** STT-deltas (geen alleen-bij-stop) |
| LLM-toegang nu | Alleen via bestand; geen interne live-API |
| Na stop | Melding met pad (console + messagebox) |

## Scope

### In scope

- Transcript-writer module/helpers onder Meeting Buddy
- Bestand aanmaken bij `orchestrator.start`
- Append bij final `TranscriptDelta`
- Header-finalisatie + flush bij `stop`
- Bestandsnaam: `YYYY-MM-DD_HHMM_<stem>.md` (agenda-stem of `meeting`)
- Locales voor meldingen; korte help-regel
- Tests voor path, markdown-opbouw, append van finals, stop-finalize

### Expliciet buiten scope

- `get_live_transcript()` / capability voor in-process LLM
- LLM-module zelf
- Partial (`is_final=False`) tekst op schijf
- Clipboard, auto-open in editor, “map openen”-knop (mag later)
- Rijke review-UI / transcriptviewer in de overlay
- Schrijven naar actieve dicteer-bestemming

## Bestandslayout

```text
{app_dir}/meeting-buddy/transcripts/
  2026-07-22_2105_MT-overleg.md
```

`app_dir` = bestaande praatMaar app-datamap (zoals voor agendas/config).

### Markdown-sjabloon (start)

```markdown
# <titel>

- Gestart: <lokaal ISO-achtig of leesbaar datetime>
- Status: lopend

## Agenda

- [ ] Opening
- [ ] …

## Transcript

```

Titel = agenda display-naam (bestandsstem / H1) of `Meeting` als onbekend.

### Tijdens de meeting

- Alleen deltas met `is_final=True` en niet-lege `text`
- Append aan het bestand na `## Transcript` (spatie of newline tussen stukken;
  implementatie kiest één consistente scheiding, bij voorkeur spatie binnen
  zin / newline bij duidelijke segmentgrenzen als STT die levert)
- Na elke append: flush (en bij voorkeur `fsync` best-effort) zodat externe
  readers recente bytes zien
- Schrijffouten: loggen; meeting en overlay gaan door

### Bij stop

- Statusregel → `gestopt`
- Regel `Gestopt: <datetime>` toevoegen
- Agenda-checkboxes bijwerken waar `TopicStatus.DISCUSSED` bekend is
  (`[x]` / `[ ]`)
- Bestand sluiten/flushen
- Melding: i18n-tekst met absolute pad (messagebox + console/print)

Lege sessie (geen finals): bestand met header blijft staan; melding alsnog.

## Integratie

```text
MeetingOrchestrator.start
  → TranscriptJournal.create(app_dir, title, agenda_topics)
  → path bewaren op orchestrator/module

on_stt_event (TranscriptDeltaReceived, is_final)
  → TranscriptJournal.append(text)

MeetingOrchestrator.stop / module.stop_meeting
  → TranscriptJournal.finalize(topics, ended_at)
  → UI melding met path
```

Voorgestelde eenheid: `modules/_builtin/meeting_buddy/transcript_journal.py`
(pure file I/O + markdown helpers; makkelijk unit-testbaar zonder Tk).

Overlay toont **geen** volledig transcript (bestaande productregel blijft);
alleen opslag op schijf.

## Observability

- Log events zonder volledige transcripttekst in standaardlogs (pad + bytes
  geschreven / foutcode volstaan), consistent met bestaande privacy-houding.

## Tests (richting)

- `transcripts_dir(app_dir)` onder `meeting-buddy/transcripts`
- `create` schrijft header + lege Transcript-sectie
- `append` voegt alleen finals toe; partials genegeerd
- `finalize` zet eindtijd en agenda-checkboxes
- Orchestrator/module: start→append→stop raakt journal (met fake STT / temp path)

## Success criteria

1. Vanaf meeting-start bestaat er een `.md` in de Meeting Buddy transcripts-map.
2. Final transcript-tekst groeit tijdens de sessie op schijf (zichtbaar voor
   externe readers zonder te wachten op stop).
3. Bij stop: afgeronde header + melding met pad.
4. Geen live in-process transcript-API in deze slice.

## Later (niet blocker)

- Interne `get_live_transcript()` voor LLM-module
- “Map openen” / “Bestand openen” vanuit de melding
- Optionele partial-sectie of snapshot-rewrite voor crash-recovery
