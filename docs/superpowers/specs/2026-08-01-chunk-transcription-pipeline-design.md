# Design: chunk-transcriptie-pipeline

Datum: 2026-08-01  
Status: approved (brainstorm)  
Vervangt: periodieke volle-buffer-partials + “finaal altijd volledig Whisper”
([2026-07-22-incremental-final-from-partial-design.md](2026-07-22-incremental-final-from-partial-design.md)).

## Probleem

`incremental_transcription` hertranscribeert bij elke interval de **hele** groeiende
buffer. Bij lange opnames wordt elke partial zwaarder; bij stop volgt nóg een volle
Whisper-run. De module helpt modules/events, maar niet de eindtijd of lange sessies.

## Doel

Whisper alleen over **nieuwe audio-chunks**; bij stop concatenatie van chunk-teksten
(+ laatste onaffe staart). Geen tweede volle-buffer-run. Pill toont twee LED’s die
aangeven of een knip door VAD of door het tijdvenster kwam.

## Beslissingen

| Onderwerp | Keuze |
|-----------|--------|
| Architectuur | Uitbreiden bestaande module “Incrementele transcriptie” (aanpak A) |
| Modi | `fixed`, `vad`, `hybrid` (alle drie in de module-UI) |
| Stop | Alleen chunks + staart; geen volle her-run |
| Naad-mitigatie | Overlap (~1,5 s) + conservatieve tekst-ontdubbeling |
| Pill | Twee LED’s (VAD + tijd), LCD-stijl; grijs in rust, kort oplichten bij hit |
| Migratie | Geen backwards-compat nodig (nog geen gebruikers van de oude incremental) |

## Config

| Key | Type | Default | Betekenis |
|-----|------|---------|-----------|
| `incremental_transcription` | bool | `false` | Module aan/uit |
| `incremental_chunk_mode` | `"fixed"` \| `"vad"` \| `"hybrid"` | `"hybrid"` | Knipstrategie |
| `incremental_vad_ms` | int | `2000` | Stilte om te knippen (VAD / hybrid) |
| `incremental_chunk_seconds` | float | `30` | Vaste / max chunklengte |

**Intern (niet in UI v1):** overlap-duur ~1,5 s.

### Gedrag per modus

- **fixed:** knip strikt op `incremental_chunk_seconds`.
- **vad:** knip bij stilte ≥ `incremental_vad_ms`; hard cap = `incremental_chunk_seconds`
  (voorkomt urenlange chunks als er geen stilte is).
- **hybrid:** knip bij stilte ≥ `incremental_vad_ms`, anders geforceerd op
  `incremental_chunk_seconds`.

Triggerreden voor de pill: `vad` of `fixed` (hard cap in vad-modus telt als `fixed`).

## Runtime — tijdens opname

1. Audio blijft in de bestaande `Opnamesessie`-buffer.
2. Achtergrondworker bewaakt de **open chunk** (audio sinds laatste knip).
3. Bij knip-trigger:
   - markeer reden (`vad` | `fixed`) → pill-LEDs;
   - audio = open chunk **plus** overlap van het vorige chunk-einde (niet bij eerste);
   - Whisper alleen op dat stuk;
   - conservatief ontdubbelen tegen het eind van de vorige chunk-tekst;
   - append aan `_chunk_transcripts`;
   - emit `transcript.partial` = huidige concatenatie;
   - reset open chunk (met overlap-anker).
4. Eerdere chunks worden **niet** opnieuw getranscribeerd.

### Stilte-detectie (v1)

Eenvoudige energie/RMS over frames (bestaande niveau-paden waar mogelijk).
Geen apart VAD-model. Knip wanneer aaneengesloten stilte ≥ `incremental_vad_ms`.

### Ontdubbelen (conservatief)

**Primair:** audio-overlap (~1,5 s) + conservatieve **tekst-dedupe**
(`dedupe_overlap_text`). Alleen schrappen bij identieke token-overlap
(minstens één token na NFC/casefold; interpunctie aan tokenranden telt
niet mee). Geen prefix-match (`pa` ≠ `paard`). Geen fuzzy/Levenshtein
(`inspelen` ≠ `inspreken`). Geen match → `" ".join` (liever dubbel dan kwijt).

Dedupe leest de gecommitte transcripten **bij commit**, niet bij enqueue.
De Whisper-job draagt alleen audio (inclusief overlap); `previous_text`
zit niet op de job. Incomplete woordstaarten (`pa...` / `paard`) blijven
staan — dat is een hypothese-revisie, geen identieke overlap.

Timestamp/mutable-tail-merge is bewust **niet** in de runtime: word-timestamps
waren te traag; segment-tijden gaven gaten of gestapelde hypothesen bij
vloeiend voorlezen. Helpers blijven in `chunk_transcription.py` voor later.

Help vermeldt naden als mogelijk restissue. Bridge-hertranscriptie van alleen
de naad = latere optie.

## Runtime — bij stop

1. Stop worker; pill mag niet wachten op in-flight chunk-Whisper (bestaande regel).
2. Open audio boven minimale duur → Whisper staart (+ overlap), ontdubbel, append.
3. Finaal = concatenatie van alle chunk-teksten.
4. Delivery ongewijzigd (save / plak / `transcript.final` / events).
5. Geen volle-buffer-Whisper.

**Module uit:** één Whisper over alles bij stop (huidig niet-incremental pad).

### Falen & recovery

| Geval | Actie |
|-------|--------|
| Mid-chunk Whisper faalt | Loggen, chunk overslaan, doorgaan; geen recovery-WAV per chunk |
| Stop / staart / delivery faalt | Hele sessie-WAV → `%APPDATA%\praatMaar\recovery\` (bestaand pad + UI) |
| Deels gelukt, staart faalt | Afleveren wat er is **én** recovery-WAV van de hele sessie |
| Geen geslaagde chunks | Fallback volle run waar mogelijk; bij falen recovery |

Geen nieuw recovery-formaat.

## Pill-LEDs (designstandaard)

Volgens [docs/design/pill.md](../../design/pill.md) en fidelity-pass:

**Opname-layout (module aan):**

`[ rode dot ] Opname [ waveform ] [◇ VAD] [⏱ tijd] [ modus-tag ] [ ■ ]`

- Twee kleine iconen (◇ stilte / ⏱ tijd), LCD-metafoor; grijs in rust, kleur bij hit.
  Geen anonieme bolletjes — vorm draagt betekenis.
- **Rust:** muted grijs op donkere capsule (`#202124` / tekstfamilie `#f1f3f4`).
- **Hit:** kort oplichten (~0,6–1 s), daarna terug grijs; iconen blijven zichtbaar.
- Kleuren uit bestaand HUD-palet (geen paars/neon): VAD ≈ ok/blauw-accent canvas;
  tijd ≈ amber/`#ffb020` (transcribe-familie). Exacte hex uit `indicator`-tokens.
- Alleen zichtbaar als de module **aan** is.
- Non-activating; geen transcript in de pill.

## Modules-UI & docs

- Modules-dialoog: checkbox + modus-keuze + VAD-ms + chunk-seconden.
- Copy/help nl/en/de: chunk-pipeline i.p.v. “finaal altijd volledig”; korte
  waarschuwing over chunk-naden / ontdubbelen.
- Designbrief [docs/design/modules.md](../../design/modules.md) later bijwerken
  (globale optie-tekst).

## Buiten scope (v1)

- Bridge-hertranscriptie op naden
- Overlap-duur als gebruikerssetting
- UI die partial-tekst in de pill toont
- Echte streaming-Whisper / model-prompt `condition_on_previous_text`
- Meeting Buddy-specifieke chunk-UI (zelfde pipeline via gedeelde sessie is ok)

## Tests (richting)

- Mode fixed/vad/hybrid: knipreden en LED-signalen
- Stop zonder volle her-run als chunks bestaan
- Overlap-ontdubbeling: duidelijke match vs geen match
- Chunk-falen mid-sessie + recovery bij stop-fout
- Module uit: één volle run bij stop
