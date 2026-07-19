# Design — Meeting Buddy MVP (verticale snede)

- **Datum:** 2026-07-19
- **Status:** Concept (goedgekeurd in brainstorm)
- **Basis:** RFC-MeetingBuddy-01..04, RFC-AudioCapture-01, ADR-0003,
  capability-registry / speaker-detection / module-capabilities specs

## Doel

Eerste verticale, implementeerbare snede: **microfooncapture → incrementele
transcriptie → dunne Meeting State → heuristische hints**.

Meeting Buddy is een Second Brain tijdens de vergadering, geen transcriptviewer.

## Productregel

Meeting Buddy toont alleen een hint wanneer die waarschijnlijk direct bruikbaar
is. **Twijfel → geen hint**, niet een waarschuwing.

## Scope

### In MVP

| Verantwoordelijkheid | Levert |
|----------------------|--------|
| `audio-capture` (module) | Capability `audio.continuous_capture` — continue mic op Windows |
| `transcription.speech_to_text` (capability) | Dunne incrementele wrapper op `SharedWhisper` |
| `meeting-buddy` (module) | Prep, sessie-orkestratie, Meeting State, heuristieken, hints, compacte overlay |

### Expliciet buiten MVP

- System audio / loopback / multi-source mixing
- AI-provider voor `ai.semantic_analysis` (contract mag bestaan; niet vereist)
- Rijk dashboard, review, export, multi-meeting knowledge
- Nieuwe `CycleEvent`-types
- macOS/Linux continuous capture (Windows eerst)

De volledige acceptatiecriteria van RFC-AudioCapture-01 blijven richtinggevend
voor latere audio-architectuur. Criteria voor loopback, mixing en meerdere
bronnen gelden **niet** voor deze bouwslice.

---

## Modulegrenzen & dataflow

Meeting Buddy is de **orkestrator**. `audio-capture` en STT kennen elkaar alleen
via capability-contracten. Meeting Buddy verwerkt **geen** PCM.

```text
[Tray] start/stop / agenda voorbereiden
        │
        ▼
meeting-buddy
   ├─ prepare agenda/doelen
   ├─ create meeting_session_id
   ├─ start capture session
   └─ start transcription session
        │
        ▼
audio-capture
   └─ publiceert AudioChunks via audio.continuous_capture
        │
        ▼
transcription.speech_to_text
   ├─ consumeert AudioChunks
   ├─ gebruikt SharedWhisper
   └─ publiceert TranscriptDeltas
        │
        ▼
meeting-buddy
   ├─ optionele speakerlabels koppelen (of UNKNOWN)
   ├─ heuristieken → StateProposals
   ├─ MeetingStateService muteert MeetingState
   ├─ Hint Engine evalueert
   └─ compacte overlay bijwerken

audio-capture ──status/fout──► meeting-buddy
  (geen PCM naar meeting-buddy)
```

### Verantwoordelijkheden

| Unit | Doet | Doet niet |
|------|------|-----------|
| `audio-capture` | Devices, capturesessie, ringbuffer, timestamps, AudioChunk-events | STT, hints, Meeting State, Buddy-UI |
| `transcription.speech_to_text` | AudioChunks → TranscriptDeltas, SharedWhisper-coördinatie | Devicebeheer, Meeting State, hints |
| `meeting-buddy` | Prep, orkestratie, heuristieken, state, hints, compacte UX | Raw device-I/O, Whisper-modelbeheer |
| `speaker-detection` | Optionele labels (tijdsgebonden) | Verplichte MVP-afhankelijkheid, state-mutaties |
| `SharedWhisper` | Eén modelinstantie, locking, inferentie | Productprioritering, Buddy-sessielogica |

---

## Capability-contracten

### `audio.continuous_capture` (streaming — één model)

```text
start_session(config) -> CaptureSession
subscribe_audio(session_id, callback)
stop_session(session_id)
get_status(session_id)
```

- v1-bron: microfoon only; API/seams laten latere loopback toe zonder herontwerp
  van Meeting Buddy.
- Consumer van de PCM-stream: **alleen** `transcription.speech_to_text`.
- Meeting Buddy subscribe’t op **status/fouten**, niet op audio-callbacks
  (tenzij later expliciet nodig voor correlatie — niet in MVP).

### `transcription.speech_to_text`

Consumeert `AudioChunk`s; produceert `TranscriptDelta`s.

### `audio.speaker_detection` (optioneel)

MVP-default: `speaker = UNKNOWN`.

Als de capability meedoet: parallel op dezelfde `AudioChunk` / audiosessie
(niet na tekst). Meeting Buddy koppelt via timestamps of chunk-ID.

```text
AudioChunk
   ├─ transcription.speech_to_text
   └─ audio.speaker_detection   (optioneel)

TranscriptDelta + SpeakerLabel  →  meeting-buddy
```

### `ai.semantic_analysis`

Interface + eventuele contracttest toegestaan. **Geen** stub die nodig is voor
normaal gebruik. Heuristieken zijn het primaire pad.

---

## Sessie-eigenaarschap

Drie sessies; Meeting Buddy orkestreert en bewaart de koppeling.

```text
MeetingSessionBinding
- meeting_session_id          # eigendom meeting-buddy
- capture_session_id          # eigendom audio-capture
- transcription_session_id    # eigendom STT
```

- Dicteer-`session_id` / `CycleEvent` blijven apart; geen CycleEvent-uitbreiding.
- Alle `AudioChunk`s, `TranscriptDelta`s, speakerlabels en hints dragen minimaal
  hun eigen sessie-ID en tijdreferentie.

---

## TranscriptDelta-contract

```text
TranscriptDelta
- session_id          # transcription_session_id
- sequence            # monotoon stijgend per sessie
- start_ms
- end_ms
- text
- is_final            # false = voorlopig; true = vast voor dit interval
- confidence
```

### Chunk-beleid (MVP-getallen)

| Parameter | Waarde | Toelichting |
|-----------|--------|-------------|
| Max chunkduur | 3000 ms | Audio naar STT per venster |
| Overlap | 500 ms | Beperkt woordknippen op grenzen |
| Timestamping | `start_ms`/`end_ms` t.o.v. capture-sessie-start | Correlatie met labels |
| Non-final | Mag tekst herzien voor dezelfde tijdsrange | UI/heuristiek gebruikt laatste |
| Final | Vervangt eerdere non-finals die overlapen op `[start_ms, end_ms]` | Geen dubbele commits naar state |
| Late correctie | Nieuwe delta met hoger `sequence`; `is_final=true` | Heuristieken zien `source_delta_ids` |

Exacte sample rate volgt capture-config (typisch 16 kHz mono, gelijk aan dictee).

---

## SharedWhisper-prioriteit & backpressure

**Prioriteit:** actief dictee gaat vóór Meeting Buddy-chunks.

| Regel | Gedrag |
|-------|--------|
| Dictee actief | Buddy-chunks in korte wachtrij; dictee mag niet crashen of blokkeren |
| Achterstand | UI: “Transcriptie loopt achter”; geen stille drops |
| Capture | Blijft lopen zolang ringbuffer capaciteit heeft |
| `max_whisper_queue_duration` | 10 s — daarboven degradatie |
| `max_audio_buffer_duration` | 30 s — daarboven degradatie |

**Degradatie bij overschrijding (expliciet):**

1. Hints tijdelijk pauzeren
2. Transcriptieachterstand melden in overlay
3. Oudste nog niet verwerkte audio gecontroleerd overslaan
4. **Gap-event** registreren (zichtbaar in status; geen stille data loss)

---

## Meeting State

Hints zijn **afgeleid**, geen bron van waarheid. Een hint verwijst naar state of
observaties.

```text
MeetingState
- topics[]                # uit agenda_items + handmatig
- goals[]                 # optionele doelenregels uit prep
- questions[]
- action_items[]          # candidates tot bevestiging
- emitted_hints[]         # afgeleid; nooit bron van waarheid
```

### Entities

```text
Topic
- id
- title
- status: open | discussed
- source: agenda | manual
- confidence
- last_matched_at

Question
- id
- text
- status: open | possibly_answered | answered | dismissed
- source_delta_id
- created_at
- resolved_at
- confidence
  # Timeout expireert de Question niet; alleen hint-cooldown dempt herhaalde meldingen.

ActionItem
- id
- description
- owner: string | UNKNOWN
- status: candidate | confirmed | dismissed
- source_delta_id
- confidence
```

Actiepunten starten als **candidate**. Heuristiek bevestigt niet autonoom.

### Mutatielaag

```text
TranscriptDelta → Heuristics → StateProposal → MeetingStateService → MeetingState
```

```text
StateProposal
- proposal_id
- meeting_session_id
- type
- payload
- source_delta_ids
- confidence
- created_at
```

Geen directe veldschrijfs vanuit losse heuristieken.

**Niet in MVP-state:** deelnemersmodellen, besluitenregister, risico’s,
documentreferenties, multi-meeting knowledge, zware confidence-aggregatie.

---

## Heuristieken

### Topic matching

- Normaliseer hoofdletters en leestekens; strip stopwoorden
- Tokens + herkenbare frases
- Match over een kort venster van recente deltas
- Eisen (startwaarden, tunebaar): `topic_match_score >= 0.55` **én**
  `matched_tokens >= 2` (of 1 als die token een volledige genormaliseerde
  topic-frase dekt van ≥ 3 tekens)
- Matchvenster: laatste 45 s aan deltas
- Eén toevallig woord sluit geen topic
- Na voldoende match: status `discussed` (later eventueel tussenstatus `active`)

### Open vragen

Trigger op `?` **én** NL-vraagpatronen, o.a.:

`wie`, `wat`, `waar`, `wanneer`, `waarom`, `hoe`, `kunnen we`, `moeten we`,
`is het`, `hebben we`, `wat doen we met`

Gedrag:

- Openen bij patroonherkenning
- Bij latere tekst met voldoende overlap binnen tijdsvenster → `possibly_answered`
- Definitief `answered` alleen na handmatige dismiss/bevestiging of een **expliciete**
  sterke antwoordregel (geen vage “antwoord-heuristiek”)
- Timeout sluit de vraag **niet**; voorkomt alleen herhaalde hints (cooldown)

### Actiepunten (candidate)

Patronen o.a.: `ik pak …`, `jij doet …`, `kun jij …`, `actiepunt …`,
`we moeten nog …`, `laten we …`

Hint-voorbeeld: “Mogelijk actiepunt: websitecontrole uitvoeren.”  
Gebruiker: bevestigen / aanpassen / negeren.

---

## Hint Engine

Niet elk open state-item wordt automatisch een hint. Timing, confidence en
cooldown beslissen.

### MVP-hinttypen (exact drie)

| Type | Betekenis |
|------|-----------|
| `topic_not_discussed` | Agendapunt nog niet besproken |
| `question_open` | Open vraag lijkt onbeantwoord |
| `candidate_action_without_owner` | Mogelijk actiepunt zonder eigenaar |

```text
Hint
- id
- type
- message
- priority
- confidence
- related_entity_id
- created_at
- expires_at
- cooldown_key
- status: active | dismissed | expired
```

### Hint-parameters (MVP)

| Parameter | Waarde |
|-----------|--------|
| Max gelijktijdig zichtbaar | 3 |
| Visuele nadruk | Exact één hint met hoogste prioriteit |
| Twijfel | Geen hint |
| Per type | Eigen trigger, min. wachttijd, cooldown, dismiss |

Concrete drempels (startwaarden; tunebaar in module-config):

| Type | Min. wachttijd | Cooldown |
|------|----------------|----------|
| `topic_not_discussed` | 120 s na start (of na laatste match-poging) | 180 s per topic |
| `question_open` | 60 s na openen vraag | 120 s per question |
| `candidate_action_without_owner` | 5 s na candidate | 90 s per action |

---

## UX

```text
Tray → Modules
  ├── Meeting starten
  ├── Meeting stoppen
  └── Agenda voorbereiden
```

### Compacte overlay (geen transcript)

- Regel status: Meeting actief · timer
- Tot 3 hints (één met hoogste nadruk)
- Controls: **dismiss**, **bevestig** (waar relevant), **minimaliseer**
- Altijd zichtbaar: capture (actief/fout), transcriptie (actief/vertraagd/uit),
  sessie actief

Geen transcriptweergave, geen volledige state-lijsten, geen rijk dashboard.

### Prep

- Één tekstveld; gebruiker kan vóór start corrigeren
- Één niet-lege regel → één topic
- Lege regels negeren; bullets/nummering strippen

Voorbeeld:

```text
1. Stand van zaken planning
2. Budget
- Beveiligingsrisico’s
Besluit over livegang
```

→ topics: Stand van zaken planning; Budget; Beveiligingsrisico’s; Besluit over livegang.

---

## Fail-soft

| Situatie | Gedrag |
|----------|--------|
| Geen capture / start faalt | Sessie start niet; duidelijke fout |
| Geen speaker detection | `UNKNOWN` |
| Geen AI-provider | Heuristieken blijven werken |
| Whisper bezet (dictee) | Wachtrij + backpressure (zie hierboven) |
| Capture valt mid-sessie uit | Buddy blijft open; fout; reconnect aanbieden |
| STT valt uit | Capture binnen `max_audio_buffer_duration`; daarna expliciete gap |
| Dicteerfout in Buddy-pad | Mag dictee nooit laten crashen |

---

## Testbaarheid (MVP)

- Unit: buffering, delta final/non-final merge, topic match scoring, vraag-/actiepatronen
- Unit: Hint Engine (cooldown, max 3, twijfel→geen hint)
- Unit: StateProposal → MeetingStateService
- Integratie: capture → STT → deltas (mic of fake AudioChunks)
- Contracttests: `audio.continuous_capture`, `transcription.speech_to_text`
- Prioriteit: dictee vs Buddy-queue (simulatie lock)
- Geen stille drops: gap-events asserten bij degradatie

---

## Relatie tot RFCs

| RFC | Rol t.o.v. deze slice |
|-----|------------------------|
| MeetingBuddy-01 | Visie behouden; MVP bewijst “geen transcriptviewer” |
| MeetingBuddy-02..04 | Architectuurprincipes; roadmap herschikt (hints eerder dan rijk dashboard) |
| AudioCapture-01 | Infrastructuurrichting; MVP = mic-only subset als module + capability |

---

## Open voor latere slices (niet blokkerend)

- WASAPI loopback + mixer (RFC-AudioCapture)
- Lokale `ai.semantic_analysis`-provider
- Review / export / rijkere state
- macOS capture
- Tussenstatus `active` voor topics
