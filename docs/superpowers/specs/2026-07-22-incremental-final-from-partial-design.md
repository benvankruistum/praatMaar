# Design: incrementeel finaal uit laatste partial

Datum: 2026-07-22  
Status: approved

## Probleem

`incremental_transcription` draait Whisper periodiek tijdens opname en emitteert
`transcript.partial`, maar bij stop wordt de hele buffer opnieuw getranscribeerd.
Dat maakt de feature nuttig voor externe consumers, niet voor snellere eindtijd.

## Beslissing (optie C)

Bij stop met incrementele transcriptie **aan** en minstens één geslaagde partial:

- gebruik de **laatste partialtekst** als finaal transcript;
- **geen** nieuwe Whisper-run;
- audio ná die partial (vaak ≤ ~interval) wordt **niet** meegenomen.

Zonder partial (te kort / eerste cycle nog niet klaar): fallback naar volledige
Whisper zoals nu. Incremental uit: ongewijzigd.

## Gedrag

### Tijdens opname

Ongewijzigd: ~elke 3 s Whisper over de hele buffer → `transcript.partial`.
Sessie onthoudt de laatste niet-lege partialtekst (gewist bij start/cancel).

### Bij stop

1. Incremental worker stoppen (join met timeout), zodat een in-flight partial
   nog kan landen als laatste tekst.
2. Als laatste partial aanwezig: eindpad met die tekst (bestemmingscommando,
   save, plakken, events) **zonder** `model.transcribe`.
3. Anders: bestaande `_transcribe_audio` over alle chunks.

Eventketen blijft: `cycle.transcribing` → `cycle.completed` /
`transcript.saved` / … (geen nieuw event-type). Partials blijven tussentijds;
finaal is de gekozen partialtekst (of volle Whisper-fallback).

## Buiten scope

- Staart apart transcriberen en plakken (optie A)
- UI die partials toont
- Wijziging van interval/min-seconden defaults

## Tests

- Met partial + stop → geen extra Whisper-call; save bevat partialtekst
- Zonder partial + stop → wel Whisper
- Incremental uit → wel Whisper
- Partials blijven events zonder save tijdens opname

## Docs

Help nl/en/de + modules-design/integration + i18n-label: uitleggen dat eindtijd
sneller kan en dat de laatste seconden na de partial kunnen ontbreken.
