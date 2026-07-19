# Design — Speaker Detection module (v1)

- **Datum:** 2026-07-19
- **Status:** Geïmplementeerd
- **Capability:** `audio.speaker_detection`
- **Basis:** [capability-registry design](2026-07-19-capability-registry-design.md)

## Doel

Zelfstandige module die transcriptsegmenten verrijkt met sprekerinformatie, zonder
koppeling aan Meeting Buddy of andere consumers. Consumers vragen uitsluitend de
capability op via `ctx.capabilities`.

## V1 — brongebaseerd

| Audio        | Rol     | confidence |
| ------------ | ------- | ---------- |
| Microfoon    | ME      | 1.0        |
| Systeemaudio | OTHER   | 1.0        |
| Onbekend     | UNKNOWN | 0.0        |

Geen diarization, geen stemprofielen, geen biometrie. Sessie-state alleen in RAM.

## Contract

Gedeeld protocol: `modules/capabilities/speaker_detection.py`

- Input: `TranscriptSegment` (+ optioneel sessie-fallback via `observe_audio`)
- Output: `SpeakerAssignment` (`speaker_id`, `role`, `confidence`)

Implementatie: `modules/_builtin/speaker_detection.py` (`SourceBasedSpeakerDetection`).

## Module

| Eigenschap | Waarde |
|------------|--------|
| ID | `speaker-detection` |
| Default | **uit** |
| Capability owner | `audio.speaker_detection` |

Lifecycle:

1. `on_app_start` — registreert provider in de registry
2. `on_event` — `CYCLE_STARTED` → `start_session` + `observe_audio`; `CYCLE_IDLE` → `stop_session`
3. `on_app_shutdown` — service vrijgeven; registry ruimt capability op via `unregister_owner`

Mapping `CycleEvent.source` → `AudioSource`:

- `live` → microfoon (huidige dicteercyclus)
- `system` → systeemaudio (toekomst)
- overig (bijv. `recovery`) → unknown

## Consumer-gedrag

Consumers gebruiken `get()` (optioneel) of `require()` (verplicht). Bij ontbrekende
capability of provider-fout: `role=UNKNOWN`, `confidence=0` — consumer blijft werken.

Voorbeeld: `MeetingBuddyConsumer` in `tests/test_capability_lifecycle.py`.

## Foutafhandeling

Detectie-fouten (onbekende bron, ontbrekende sessie, provider-exception) →
`UNKNOWN` / `confidence=0`. Geen crash in consumerende modules.

## Buiten scope (v1)

- Speaker diarization / clustering / embeddings
- Permanente stemprofielen
- Meeting Buddy productmodule
- CycleEvent-schema-uitbreiding

## Roadmap

| Versie | Inhoud |
|--------|--------|
| V1 | Capability + brongebaseerd ME/OTHER/UNKNOWN |
| V2 | Speaker clustering |
| V3 | Diarization |
| V4 | Optionele persoonsidentificatie |

## Acceptatiecriteria

- [x] Zelfstandige module (`speaker-detection`)
- [x] Capability `audio.speaker_detection` geregistreerd
- [x] Geen Meeting Buddy vereist
- [x] Werkt zonder AI
- [x] Consumers kunnen capability optioneel gebruiken
- [x] Geen persoonsgegevens opgeslagen
