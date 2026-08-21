# Design: unprocessed audio-staart (reviseable tail, slice A)

Datum: 2026-08-20  
Status: accepted (2026-08-20)  
Owners: `audio-speech` (pipeline), `core-python-architect` (`Opnamesessie` / dicteercyclus)  
Consult: `ux-product-design` (live partial mag achterlopen; geen replace-UI in deze slice)

Gerelateerd: [chunk-transcription-pipeline-design](2026-08-01-chunk-transcription-pipeline-design.md), [chunk-merge-postmortem](2026-08-20-chunk-merge-postmortem.md).

## Probleem

Met vaste 20 s-chunks en commit-time tekst-dedupe is de woordsalade weg en is
`stop_join` laag. Op de knip blijft een **incomplete hypothese** staan
(`brandende...` + later `torts`), omdat Whisper de laatste seconden van een
chunk als afgekapte tekst commit vóór de volgende audio er is.

Vergroten van overlap zonder de staart te herzien maakt dat erger: chunk B
herdecodeert meer audio en plakt een tweede hypothese achter A’s afgehakte
suffix. Prefix-dedupe op `pa`/`paard` is bewust uitgesloten.

Een eerdere mutable tail van ~1,5 s op **segment-timestamps** wist het midden
of stapelde hypotheses. Die dead path (`merge_timed_chunk`) niet opnieuw
aansluiten.

## Doel

Incrementele finalisatie: 90–95 % van de audio tijdens spreken Whisperen, bij
stop alleen de korte onverwerkte staart. Live preview mag 4–8 s achterlopen.
Eindtranscript (opgeslagen `.txt`) mag geen afgehakte+herstart-naad meer
tonen van het type `brandende... torts`.

Scheduling en transcript-consistentie zijn ontkoppeld: **cut** plant
Whisper-vensters; **committed** markeert alleen audio die écht is getranscribeerd.

## Productkeuze (goedgekeurd)

**A — achterlopen, niet live vervangen.** Alleen confirmed tekst naar
`transcript.partial` en (indien aan) live-plak. Geen `replace_tail` in het
OS-invoerveld in deze slice.

## Niet in deze slice

- Live revisie van al getoonde tekst (optie B)
- Bridge-Whisper / word-timestamps op de naad
- Fuzzy of prefix-token-dedupe
- `merge_timed_chunk` weer wiren
- Overlap in de UI; overlap blijft intern 1,5 s
- Terug naar agressieve VAD als default
- Rolling window los van deze staart (kan later)

## Twee cursors

| Cursor | Betekenis | Mag bij Whisper-falen opschuiven? |
|--------|-----------|-----------------------------------|
| **cut** (`_transcribed_through_samples`) | Laatste knip; decide-loop meet open chunk t.o.v. deze cursor (20 s-cadans) | Ja — scheduling gaat door |
| **committed** (nieuw, sample-index) | Tot hier is audio Whisper’d **en** gecommit | **Nee** |

Decide-loop: `open = total - cut` (ongewijzigd).  
Hold/whisper-helper: `available = cut_end - committed` (niet `cut_end - through`).

Na de eerste hold is dat het verschil: `cut = 20 s`, `committed = 14 s`; bij
de cut op 40 s is **26 s** nog niet definitief, niet 20 s. De vraag “kan ik
veilig 6 s achterhouden?” hoort bij `committed`, niet bij de cut-cadans.

## Vensterberekening (pure helper, samples)

Constanten: `OVERLAP_SECONDS = 1.5`, `UNPROCESSED_TAIL_SECONDS = 6.0`.  
`min_hold_available = tail_samples + 2 * overlap_samples`.

Gegeven `committed`, `cut_end`, `sample_rate`:

1. `available = cut_end - committed`.
2. Als `available < min_hold_available`: **geen hold**, `commit_end = cut_end`
   (korte VAD-knip mag het midden niet in een staart parkeren).
3. Als `available == min_hold_available`: **wel hold** (`>=` — grens gaat in
   hold; vastgelegd in een unit test).
4. Anders `commit_end = cut_end - tail_samples`.
5. `slice_start = 0` als `committed == 0`, anders
   `max(0, committed - overlap_samples)`.
6. Whisper `[slice_start, commit_end)`.

Steady state bij 20 s-cadans + hold 6 s + overlap 1,5 s: venster **~21,5 s**,
niet 20 s. Dat is bewust.

```
cut 20 / 40 / 60 / 80 s, hold 6 s, overlap 1,5 s, 16 kHz:

commit_end:  14, 34, 54, 74 s
slice_start:  0, 12.5, 32.5, 52.5 s
```

De frase op de oude knip (`brandende toorts`) zit in het **midden** van run B,
niet als gecommitte afkapping van run A.

## Commit-semantiek

Whisper draait **buiten** de lock (bestaand). Daarna:

```
raw = whisper(slice)
if success and raw:
    lock:
        delta = dedupe_overlap_text(join(_chunk_transcripts), raw)
        append delta
        committed = commit_end   # alleen hier
    emit partial / live-plak delta
else:
    committed ongewijzigd
    cut mag al op cut_end staan
```

Een mislukte run markeert audio **niet** als verwerkt. De volgende cut neemt
het gat mee: `committed = 14`, `cut = 40` faalt; next `cut = 60` → venster
`[12.5, 54)` — groter dan normaal, geen stille 20 s-drop.

`commit_end` voor de job wordt bij enqueue berekend en meegegeven; bij falen
wordt die waarde genegeerd voor de cursor.

## Stop-pad

```
if committed == 0:
    transcribe [0, end]
else:
    transcribe [max(0, committed - overlap), end]
```

Dedupe tegen actuele `_chunk_transcripts`, append, deliver. Geen
volle-buffer-run als er al gecommitte chunks zijn. Korte opname
(`committed == 0`) blijft één run over alles.

## Live gedrag

- `transcript.partial` = concatenatie van gecommitte stukken.
- Live-plak plakt alleen die delta’s.
- De laatste ~6 s spraak is nog geen tekst; daarna in één stuk.

## Config

Geen nieuwe gebruikerssetting in v1.

| Constant | Waarde |
|----------|--------|
| `OVERLAP_SECONDS` | 1,5 (ongewijzigd) |
| `UNPROCESSED_TAIL_SECONDS` | 6,0 |

Werkpunt: knipmodus **vast**, chunk **20 s**, live-plak uit,
`condition_on_previous_text` uit.

## Latency-invariant

`stop_join` alleen is onvoldoende (één take kan groene stop hebben terwijl
de queue groeit). Per commit-venster loggen:

`processing_ratio = whisper_seconds / audio_window_seconds`

Invariant voor een lang gesprek: **gemiddelde ratio < 1,0**, liefst
**< 0,8–0,9**. Steady-state venster is ~21,5 s; als Whisper realtime is,
bouwt de wachtrij alsnog op. Bestaande `cycle.timing` uitbreiden of een
regel `chunk.whisper` per job; environment card bij `/whisper-evaluation`.

## Falen

| Geval | Actie |
|-------|--------|
| Whisper commit-venster faalt | Loggen; `committed` blijft; `cut` mag doorschuiven; volgende venster dekt het gat |
| Stop / staart faalt | Bestaande recovery-WAV van de hele sessie |
| Opname korter dan één knip | `committed == 0` → `[0, end]` |

## Tests (seams)

Pure helper:

- Eerste 20 s-cut → `commit_end = 14 s`, `slice_start = 0`.
- Tweede 40 s-cut, `committed = 14 s` → `slice_start = 12,5 s`, `commit_end = 34 s`.
- Lang: cuts 20/40/60/80 → commit_ends 14/34/54/74, starts 0/12,5/32,5/52,5
  (vangt cursor-drift).
- `available == tail + 2×overlap`: hold **wel** (`>=`).
- `available < tail + 2×overlap`: geen hold, `commit_end = cut_end`.

Worker / sessie:

- Eerste job audio tot ~14 s, niet 20 s.
- Whisper-falen: `committed` ongewijzigd; volgende job start nog vanaf oude
  committed − overlap.
- Stop met `committed == 0`: hele buffer. Stop met `committed > 0`: vanaf
  `committed - overlap`.
- Finale tekst bevat de hold-regio één keer.

Geen test die `pa`/`paard` gelijk verklaart.

## Acceptatie

Twee-pc-A/B, Pegasus/Pandora-naad:

- Unchunked ≈ modelplafond (namen mogen blijven schelen).
- Chunked 20 s vast + deze slice: geen `brandende... torts` in het
  **opgeslagen** `.txt`.
- `stop_join` in de orde van de huidige 20 s-take.
- Gemiddelde `processing_ratio` < 1,0 op een gesprek ≥ ~80 s (vier cuts).
- Live mag achterlopen; dat is geen fail.

Follow-up (2026-08-20, zelfde slice): één identiek overlap-token mag
weg (`Prometheus. Prometheus.`). Geen prefix-dedupe `pa`/`paard`. Geen
bridge-Whisper in deze stap.

## Open (later)

- Bridge als de knip *vóór* de hold nog afkapt.
- Optie B: live replace van de staart.
- Tail-duur als setting.
- Rolling window als `processing_ratio` structureel ≥ 1,0.
