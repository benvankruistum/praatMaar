# Design — capability registry (module-to-module services)

- **Datum:** 2026-07-19
- **Status:** Geïmplementeerd (branch `feat/shared-whisper` / capability-uitbreiding)
- **Basis:** module-capabilities (acties, shutdown, ui_dispatch, SharedWhisper)

## Doel

Modules kunnen **services** aan elkaar aanbieden zonder directe imports tussen
concrete module-packages. Eerste toepassing: `audio.speaker_detection` voor
latere Meeting Buddy / transcriptie-modules.

## Kern

| Concept | Keuze |
|---------|--------|
| Registry | Eén `CapabilityRegistry` per app-run, via `ModuleContext.capabilities` |
| Lookup | `get()` → `None` of provider; `require()` → exception |
| Ownership | Max. één provider per capability-ID; `unregister_owner` bij shutdown |
| Threading | `RLock` rond alle mutaties/reads |
| Foutisolatie | Registry voert geen provider-methoden uit; consumer vangt fouten af |

## Contracten

Gedeelde protocollen onder `modules/capabilities/` (niet in `_builtin`):

- `registry.py` — `CapabilityRegistry`, `CapabilityUnavailableError`
- `speaker_detection.py` — `SpeakerDetectionCapability`, `SpeakerRole`, …

## Lifecycle

1. `load_enabled_modules(..., capabilities=shared)` → modules `register` in `on_app_start`
2. `shutdown_modules(..., capabilities=shared)` → `on_app_shutdown` + **altijd**
   `unregister_owner` (ook bij shutdown-fout)

## Eerste provider

`SpeakerDetectionModule` (`speaker-detection`, default **uit**): brongebaseerd
ME / OTHER / UNKNOWN. Geen Meeting Buddy-productmodule in deze PR — consumer-
gedrag is getest via `MeetingBuddyConsumer` in tests.

## Buiten scope

Meerdere providers, DI-framework, Meeting Buddy-product, stemprofielen,
CycleEvent-uitbreiding.
