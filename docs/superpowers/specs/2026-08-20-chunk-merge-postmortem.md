# Postmortem — incrementele chunk-merge vs. vloeiend voorlezen

Datum: 2026-08-20  
Branch: `cursor/chunk-timestamp-merge`  
Status: runtime terug op v1-tekst-dedupe; `merge_timed_chunk` experimenteel / niet aangesloten  
Owners voor follow-up: `audio-speech` (pipeline/kwaliteit), `core-python-architect` (Opnamesessie, live-plak-API). Consult: `ux-product-design` (reviseable staart vs. append-only plakken).

Gerelateerd: [chunk-transcription-pipeline-design](2026-08-01-chunk-transcription-pipeline-design.md), `chunk_transcription.py`, `dicteercyclus/incremental.py`, `dicteercyclus/delivery.py`.

## Samenvatting in één alinea

Incrementeel transcriberen moet **rekentijd tijdens het gesprek** benutten zodat stop **bijna direct** een goed eindresultaat geeft — niet “live als extraatje” en **niet** de hele buffer opnieuw Whisperen bij stop. Chunked decode is een **latency-optimalisatie**, geen equivalente decode van unchunked. Permanente commit van lokale hypotheses over overlappende audio maakt reconcilatie onvermijdelijk complexer dan nodig. Segment-timestamps zijn te grof voor 1,5 s overlap; word-timestamps zijn het juiste signaal maar te duur op het huidige CPU-pad. Runtime staat weer op conservatieve tekst-dedupe. Volgende architectuur: **incremental finalization** (confirmed + ruime mutable tail + alleen staart/naad bij stop), met een **reviseable** presentatie-API i.p.v. append-only live-plak.

## Productdoel (niet onderhandelen)

Doel van de module: tijdens een (lang) gesprek al transcriberen, zodat de gebruiker bij stoppen **niet** lang wacht.

Daarom is “preview tijdens opname + één volle Whisper bij stop” **afgewezen** als productlijn. Dat haalt de kernwaarde onderuit, ook al is unchunked het **kwaliteitsreferentieplafond** van het model (namen, samenstellingen). Incrementeel moet dat plafond **benaderen** met werk dat al tijdens spreken is gedaan, plus een **kleine** finalisatie (resterende staart + eventueel naad-correctie), niet 100% her-inferentie.

## Kernmodel

Een chunk-transcript is **geen stuk van het uiteindelijke transcript**. Het is een **hypothese over een tijdsgebied**. Twee geldige hypotheses over dezelfde audio (`inspelen` / `inspreken`) zijn niet betrouwbaar tot één string te mergen met tekstvergelijking.

Drie zones, niet “lijst van chunk-strings concatenaten”:

| Zone | Betekenis |
|------|-----------|
| **confirmed** | Oude audio; raak je niet meer aan |
| **mutable tail** | Laatste paar seconden; mag herdecode / replace |
| **unprocessed** | Audio die Whisper nog niet heeft gezien |

Conceptueel bij de volgende chunk: alles vóór de overlap committen; **alleen** overlap + nieuwe audio herinterpreteren. Whisper moet geen halve lettergreep (`vla...`) als enige context krijgen.

De eerdere mutable tail van **~1,5 s is te klein** (Whisper denkt in zinnen/frases). Experimentkandidaat: chunks 20–30 s, reviseable regio **4–8 s**.

## Testopzet

- Zelfde lokale Faster-Whisper, voorgelezen Nederlandse mythetekst (Pegasus / Bellerophon / Chimaera).
- A/B: incrementeel **uit** = één `transcribe` over de hele opname (referentieplafond); **aan** = hybrid/VAD of tijdvenster, overlap ~1,5 s, concatenatie.
- Unchunked-fouten (`Pekasus`, `getempt`, `zwief`) zaten in **beide** paden → modelplafond, geen merge-bug.
- Chunked extra’s: duplicaten, afhakers (`vla...`), later gaten of gestapelde hypotheses.

| Knop | Effect |
|------|--------|
| Incrementele transcriptie | Pad: concatenatie vs. één run |
| Voortbouwen op vorige tekst | Decoder-loops; standaard uit |
| Model / beam / taal | Plafond, niet de naad-herhalingen |
| Chunklengte / VAD-ms | Aantal naden; voorlezen triggert VAD op zinspauzes |
| Live-plak | Append-only delta’s; revisies stapelen in het doelveld |

## Tijdlijn van experimenten

### 0. Baseline v1

Audio-overlap 1,5 s. Merge = `dedupe_overlap_text` op `str.split()` (punctuatie blijft aan het token).

- `deze feature.` + `deze feature op twee plekken` → `feature.` ≠ `feature`
- `inspelen` vs `inspreken` (twee hypotheses, zelfde audio)

Tekst-dedupe kan nooit betrouwbaar bepalen of die twee tokens dezelfde audio zijn. Fuzzy/Levenshtein daarvoor is **niet** gewenst (echte deleties).

### 1. Word-timestamps, overlap van B droppen

Tokens met `start < overlap` in B weggooien. Pegasus-naad `gevleugelde`/`leugende` is tijd-oplosbaar.

**Gemeten:** `path=chunk record=74.4s stop_join=99.7s whisper=3.5s`. Alignment per hele chunk → backlog. Unchunked was eerder klaar.

**Kwaliteit:** afhakers bleven. Drop-B bewaart A’s afgekapte staart en gooit B’s betere overlap-decode weg.

### 2. Confirmed + mutable tail op segment-tijden (~1,5 s)

`vla...` → `vlammen` als B de staart vervangt. Geen `word_timestamps`.

**Faal 2a:** korte VAD-chunks + hold ≈ alle nieuwe audio in de staart → midden gewist (schip, tempel, droom).

**Faal 2b:** lang Whisper-segment `start=0` over overlap+nieuw → hele zin gedropt (`Hij liep en hij liep…`).

### 3. Straddlers bewaren

Chunked **erger** dan v1: hypotheses gestapeld (`Vlieg nu! Vlieg nu!`, drie keer `naast hem stond`). Segment-granulariteit + append-only live-plak = woordsalade.

### 4. Terugrol

Runtime: overlap-audio + `dedupe_overlap_text`. `merge_timed_chunk` / `TimedWord` blijven in `chunk_transcription.py` + tests, **niet** aangesloten, tot een benchmark definieert wat “beter” is.

## Wortels

1. **Semantiek:** permanente commit van lokale decodes over overlappende tijd → distributed reconciliation i.p.v. één globale decode.
2. **1,5 s overlap vs. Whisper-frases.** Segment-timestamps te grof; word-timestamps te duur op het hele chunk.
3. **Mutable tail te kort** in het experiment; bovendien werd “hold” bij korte knippen de hele nieuwe regio.
4. **Presentatie append-only.** Live-plak is geen bijzaak: als de UI alleen `append_text(delta)` kan, stapelen artefacten ook als de backend intern herziet. Incrementele ASR vereist dat de **laatste tekst reviseable** is (`confirmed` + `provisional`, of `replace_tail`).
5. **VAD op voorlezen** maakt extra naden; unchunked heeft er nul.
6. Verkeerde tussenconclusie “dan maar volle her-run bij stop” botst met het productdoel (weinig wachten na stop).

## Huidige code

| Pad | Gedrag |
|-----|--------|
| Incrementeel uit | Eén Faster-Whisper over de hele buffer bij stop (referentieplafond) |
| Incrementeel aan | Chunks + 1,5 s overlap + exacte tekst-dedupe; stop = concatenatie + onaffe staart |
| Live-plak | Chunk-delta’s appenden; geen tail-replace in het doelveld |

## Architectuur om na te streven: incremental finalization

```
tijdens gesprek:
  audio → chunks (bv. 20–30 s) → snelle decode
       → commit alles vóór overlap
       → mutable tail (bv. 4–8 s) blijft herzienbaar
       → UI: confirmed + provisional (niet append-only)

bij stop:
  unprocessed staart + eventueel laatste naad (bridge)
       → kleine Whisper-run(s)
       → eindtranscript, preview-staart vervangen
```

Bridge-hertranscriptie past hier: niet de hele opname, maar bv. 2–4 s vóór + 2–4 s na een naad (of alleen bij stop de laatste naad). Extra compute alleen waar chunking onzekerheid introduceert. Dat is 90–95% werk tijdens spreken, seconden afronding bij stop.

Datamodel intern: hypotheses over `[start_ms, end_ms]`, niet een groeiende `list[str]` die je `" ".join`.t. Confirmed prefix niet herschrijven.

## Presentatie-API (apart van decode)

Fout:

```
append("glijflucht da")
append("En in een glijvlucht daalde")
```

Richting:

```
update_transcript(confirmed_text=..., provisional_text=...)
# of minimaal:
replace_tail(chars=N, with_text=...)
```

Zelfs met latere bridge blijft append-only live-plak artefacten stapelen. Goede STT corrigeert het laatste stuk terwijl je nog spreekt; dat mag stilletjes.

Live-plak naar een vreemd invoerveld (Notepad, Word) **kan** vaak niet unpasten. Dat is een platformbeperking: ofwel geen live-plak van de provisional staart (alleen confirmed), ofwel alleen live in een eigen overlay/transcriptvenster dat wel replace ondersteunt. Niet doen alsof `host.paste()` een reviseable buffer is.

## Goedkope v1-winst (mag nu, zonder nieuwe architectuur)

Normaliseer **alleen voor matchen**, output blijft originele Whisper-tekst:

- Unicode-normalisatie, casefold
- interpunctie aan tokenranden negeren
- whitespace normaliseren

Lost `feature.` / `feature`, `zijn.` / `zijn`, `van...` / `van`. **Geen** fuzzy match op `inspelen`/`inspreken`. Tests: `tests/test_chunk_transcription.py`.

## Prioritering voor de ontvanger

1. Bevestig productdoel: incremental finalization (weinig wachten bij stop), unchunked = referentieplafond, geen volle her-run als default-final.
2. Maak live-output reviseable (of plak alleen confirmed); treat append-only als architectuurfout, niet als UX-detail.
3. Veilige token-normalisatie in `dedupe_overlap_text`.
4. Vaste WAV-evaluatieset (`/whisper-evaluation`); meet WER, duplicaten, deleties, `stop_join` vs. `whisper`.
5. Daarna bridge-hertranscriptie + grotere mutable tail (4–8 s) op die set.
6. Alleen als die finalisatie productmatig te lang is: verder in word-alignment op de overlap-strip. `merge_timed_chunk` niet opnieuw aansluiten zonder vooraf gedefinieerde drempels.

Niet doen: `condition_on_previous_text` aan tegen naden; overlap naar 0; Levenshtein tussen chunk-naden; segment-heuristieken opnieuw op live voorlezen zonder fixtures.

## Evaluatie

Skill `/whisper-evaluation`. Fixtures: korte zin; Pegasus-alinea’s (publiek/toestemming, geen echte user-audio in git); stilte voor/na. Environment card verplicht.

`Select-String -Path "$env:APPDATA\praatMaar\praatMaar.log" -Pattern "cycle.timing"`

Win = minder naden **en** geen gaten **en** `stop_join` in de orde van staart/bridge, niet van de hele opname.

## Repro

1. Zelfde model/beam/taal.
2. Incrementeel aan vs. uit; live-plak uit voor A/B van het **opgeslagen** transcript.
3. Zelfde alinea voorlezen; vergelijken met bron + unchunked.
4. Hoge `stop_join` bij `path=chunk` = wachtrij, niet de staart-Whisper.

## Open vragen

- Kan live-plak naar het OS-invoerveld ooit reviseable, of alleen confirmed-delta’s + eigen overlay voor provisional?
- Default knip: `fixed` 30 s i.p.v. hybrid, voor doorlopende tekst?
- Exacte mutable-tail-duur (4 vs. 8 s) en of bridge bij elke knip of alleen bij stop.

## Conclusie voor de ontvanger

Whisper op machine B was niet “slechter”; unchunked was het plafond. Chunking voegt hypotheses over overlappende tijd toe. Die permanent appenden (backend + UI) is het probleem. Oplossing die bij het **productdoel** past: confirmed laten staan, een **ruimere** staart herzien, bij stop alleen rest + naad, en de UI niet append-only maken. Volle her-run bij stop is het verkeerde antwoord op dezelfde meting.
