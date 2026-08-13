# Design: hybride transcriptie-voortgang op de pill

Datum: 2026-08-10  
Status: approved  
Vervangt deels: [2026-07-22-transcription-progress-design.md](2026-07-22-transcription-progress-design.md)
(segment-only % → hybride tijd + segment)

## Probleem

Tijdens `TRANSCRIBING` volgt de pill `% = segment.end / audio_duration`.
Faster-Whisper levert segmenten pas ná VAD/feature-extractie. Gebruikers zien
daardoor ~80% van de wachttijd `0%`, daarna een sprong naar `100%`. Met
incrementele/chunk-transcriptie zet het finalize-pad alleen `0` → `100` tijdens
de staart-Whisper-run — nog erger.

Misleidende absolute % is erger dan geen %; de pill kan al indeterminate
(`progress is None`: arc + marching dots, geen balk).

## Doel

Tijdens de **finale** Whisper-run (full-pad én chunk-staart) een voortgangsbalk
tonen die:

1. meteen beweegt op basis van **verwachte duur** (audio-seconden × RTF);
2. **omhoog bijtrekt** zodra er echte segment-voortgang is;
3. nooit lang op `0%` blijft hangen.

## Beslissingen

| Onderwerp | Keuze |
|-----------|--------|
| Model | Hybride: `max(tijd-%, segment-%)` |
| Start-RTF | Vast `0.4` (Whisper-tijd ≈ 0,4× audio); geen learning in v1 |
| Tijd-% bereik | `1–95` tot afronden; `100` alleen bij klaar |
| Segment-% | Ongewijzigd: `segment.end / duration`, clamp `0–99` |
| Chunk-staart | Alleen tijd-% (geen segment-callback in `_transcribe_chunks_to_text` v1) |
| Partials / RECORDING | Buiten scope (ongewijzigd) |
| ETA in seconden | Buiten scope |
| Indeterminate fallback | Niet nodig zolang ticker loopt; bij audio `≤ 0` s: start op `1%` |

## Gedrag

1. Bij start van de Whisper-fase: start een daemon-ticker (~10 Hz) met
   `audio_seconds` = opnameduur (full) of staart-/piece-duur (chunk).
2. Ticker zet `set_transcription_progress(max(tijd, segment_floor))`.
3. Full-pad: bij elk Whisper-segment `segment_floor = transcription_percent(...)`.
4. Bij succes: stop ticker, `100%`, daarna idle zoals nu.
5. Bij fout/cancel: stop ticker in `finally`, wis of laat state-notify opruimen.
6. Console-logs op 25/50/75% blijven (op basis van getoonde %).

## Pill

Ongewijzigd contract: `set_transcription_progress` / `get_transcription_progress`.
Balk + `n %` zodra er een int is; arc + marching dots blijven.

## Owners

- Responsible: `core-python-architect` (Opnamesessie + progress helper)
- Consult: `audio-speech` (RTF-default), `ux-product-design` (pill-gedrag)

## Acceptance criteria

- **AC-01** Given een trage Whisper-mock die 250 ms wacht vóór het eerste
  segment, When stop → TRANSCRIBING, Then progress samples bevatten waarden in
  `1–95` vóór `100` (niet alleen `0` dan `100`).
- **AC-02** Given segment-% lager dan tijd-%, When beide actief, Then getoonde
  % daalt niet (`max`).
- **AC-03** Given chunk-finalize met staart-Whisper, When staart loopt, Then
  progress beweegt via tijd-% en ticker stopt in `finally`.
- **AC-04** Partials tijdens RECORDING blijven zonder progress-updates.
