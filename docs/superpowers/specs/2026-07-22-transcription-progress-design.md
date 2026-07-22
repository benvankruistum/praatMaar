# Design: transcriptie-voortgang op de pill

Datum: 2026-07-22  
Status: approved

## Doel

Tijdens `TRANSCRIBING` tonen hoe ver Whisper roughly is, zodat lange runs
niet “hangen” lijken.

## Gedrag

- Pill-label: `Transcriberen 45%` (i18n), marching dots blijven.
- % = `segment.end / audio_duration_seconds`, geclamped 0–99 tot klaar; bij
  afronden kort 100% of terug naar idle.
- Alleen bij de **finale** Whisper-run (niet bij incrementele partials tijdens
  opname).
- Console: spaarzaam, bij overschrijden van 25/50/75% één logregel.
- Thread-safe push via contract (zelfde patroon als waveform-levels).

## Buiten scope

- ETA in seconden
- Progress tijdens live partials in RECORDING
