# Design — Meeting Buddy agenda-review (fase 2 + 3)

- **Datum:** 2026-07-23
- **Status:** Geaccepteerd (grill)
- **Branch:** `feat/meeting-buddy-agenda-review`
- **Gerelateerd:**
  [2026-07-23-local-llm-module-design.md](2026-07-23-local-llm-module-design.md),
  [ADR-0004](../../adr/0004-local-first-inference.md),
  [CONTEXT.md](../../../CONTEXT.md) — `agenda-review`, agendapunt-status, meeting-fase,
  vraag-van-anderen

## Probleem

Live samenvatting (fase 1) bestaat. Agendapunten en vragen lopen nog via
heuristiek (token-overlap / regex). Gewenst: LLM beoordeelt substantiële
behandeling met een statusladder; vragen van anderen komen uit de LLM met
speaker-roles als filter.

## Beslissingen (grill)

| Onderwerp | Keuze |
|-----------|--------|
| “Behandeld” | Alleen **substantieel** besproken; noemen / opening-doorloop telt niet |
| Statusladder | `open` → `treated` → `sequential` → `confirmed` |
| Inhaal | Automatisch `treated` → `sequential` als alle voorgangers ≥ `sequential` |
| Bevestigd | Alleen na **herbespreking** na `sequential` |
| Happy path | Zelfde ladder; bij eerste punt vallen treated→sequential samen |
| Opening | LLM-fase `opening` \| `body` \| `closing`; in opening geen latere topics naar treated |
| Vragen | Alleen LLM; herformuleerd; uitsluit `SpeakerRole.ME`; `OTHER`+`UNKNOWN` ok |
| Speaker | `audio.speaker_detection` (bron); later diarization |
| Zonder LLM | Heuristiek max. `open→treated`; geen inhaal/confirmed; **geen** vraagherkenning |
| Transcript/notulen | Gescheiden (ruwe transcript vs leesbare samenvatting) |

## Capability

Nieuw analyse-kind `agenda_review` op `ai.semantic_analysis`:

- Input: transcript (met optionele speaker-rollen), agenda-topics + statussen,
  huidige meeting-fase, taal
- Output (JSON in `AnalysisResult.data`): `phase`, `topic_updates`
  (`topic_id` + target status `treated`\|`confirmed`), `questions` (teksten)

Prompts blijven in Meeting Buddy; local-llm route’t het kind via Ollama.

## State / UI

- `TopicStatus`: `open` \| `treated` \| `sequential` \| `confirmed`
- Overlay: leidraad met vier markeringen; aparte vragenlijst
- Journal-checkboxes: `[x]` bij status ≥ `sequential`

## Verificatie

- [ ] Ladder + inhaal unit-tests
- [ ] Opening blokkeert latere `treated`
- [ ] Zonder LLM: geen `add_question` uit heuristiek; topic max treated
- [ ] Met LLM: vragen filteren op ≠ `ME`
- [ ] Overlay toont statussen + vragen
