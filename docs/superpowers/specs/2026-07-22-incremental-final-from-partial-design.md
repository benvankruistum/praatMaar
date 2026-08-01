# Design: incrementeel finaal uit laatste partial

Datum: 2026-07-22  
Status: **superseded** — eerst (2026-07-25) door “bij stop opnieuw volle Whisper”;
daarna (2026-08-01) door de chunk-pipeline
([2026-08-01-chunk-transcription-pipeline-design.md](2026-08-01-chunk-transcription-pipeline-design.md)).

## Probleem

`incremental_transcription` draait Whisper periodiek tijdens opname en emitteert
`transcript.partial`, maar bij stop werd de hele buffer opnieuw getranscribeerd.
Dat maakte de feature nuttig voor externe consumers, niet voor snellere eindtijd.

## Oorspronkelijke beslissing (optie C) — ingetrokken

Bij stop met incrementele transcriptie **aan** en minstens één geslaagde partial:

- gebruik de **laatste partialtekst** als finaal transcript;
- **geen** nieuwe Whisper-run;
- audio ná die partial wordt **niet** meegenomen.

Aanname “vaak ≤ ~interval” bleek onjuist bij langere opnames (model `medium`):
elke partial hertranscribeert de groeiende buffer, dus de gap tot stop loopt op
(bijv. ~15 s missing op ~51 s opname).

## Huidig gedrag (vervanging)

- Tijdens opname: ongewijzigd — periodieke partials over de hele buffer.
- Bij stop: **altijd** `_transcribe_audio` over alle chunks (ook met partials).
- Partials blijven voor modules/event-journal; eindtekst is altijd de finale run.

## Buiten scope (ongewijzigd)

- Staart apart transcriberen en aan de partial plakken (optie A)
- UI die partials toont
- Wijziging van interval/min-seconden defaults

## Docs

Help nl/en/de + Modules-label: incrementeel = tussentijds; finaal altijd volledig.
