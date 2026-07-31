# Design — Single-mic diarization (Spreker 1/2/3)

- **Datum:** 2026-07-31
- **Status:** In implementatie
- **Capability:** `audio.speaker_detection` (contract v2)
- **Basis:** [speaker-detection design](2026-07-19-speaker-detection-design.md)

## Doel

Groepsgesprek met **één microfoon**: transcriptregels labelen als `spk_1`,
`spk_2`, … zonder te bepalen wie “ik” ben. Lokaal (ADR-0004). Geen enrollment,
geen permanente stemprofielen.

## Labeling modes

| Mode | Gedrag |
|------|--------|
| `source` | v1: microfoon→ME, system→OTHER (dicteercyclus) |
| `cluster` | Online clustering op PCM; altijd `SpeakerRole.OTHER` + `spk_n` |

Meeting Buddy start speaker-sessies in **`cluster`**. Dicteer-`CycleEvent`s
blijven **`source`**.

## Contract v2

- `TranscriptSegment.start_ms` / `end_ms` (optioneel; vereist voor cluster-hit)
- `observe_pcm(session_id, pcm_f32, start_ms, end_ms, sample_rate)`
- `set_labeling_mode(session_id, mode)`
- `SpeakerAssignment.speaker_id`: `spk_1`… of v1 `me`/`other`/`unknown`

## Clustering v1 (licht)

1. Ingest PCM (alleen nieuw audio sinds sessie-cursor; capture-overlap skippen)
2. Energie-VAD → spraakspans
3. Spectrale band-embeddings (numpy) per span
4. Online nearest-centroid (cosine); nieuwe spreker onder drempel
5. `assign_speaker`: maximale overlap van `[start_ms, end_ms]` met spans

Geen pyannote/WhisperX in v1. Geen cloud.

## Meeting Buddy

- Meeting start → `start_session` + `CLUSTER` + capture-subscribe voor PCM
- Finals → segment met delta-tijden → `LabeledFinal(speaker_id=spk_n)`
- Agenda-review format: `[spk_2] tekst`; ME-filter triggert niet (alles OTHER)

## Buiten scope

- ME-enrollment / persoonsnamen
- Zware diarization-stacks
- Dual-stream mic+loopback als primaire labelbron
