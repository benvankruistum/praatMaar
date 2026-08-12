# Product specification — Dicteerpresets (Snel / Gebalanceerd / Nauwkeurig)

## Status

**Accepted** — 2026-08-11 (thin slice; goedgekeurd als tegenvoorstel t.o.v. metende setup-wizard)

## Context

Gebruikers hebben modelgrootte en Whisper-opties, maar weten niet welke
combinatie bij hun machine/latentiestijl past. Een metende optimalisatie-wizard
is te zwaar voor v1.0; drie named presets leveren het grootste deel van de
klantwaarde zonder hardware-detectie of trial-STT.

## Problem

**User:** Nieuwe of onder-getunede dicteergebruikers  
**Situation:** Instellingen → Geavanceerd / Whisper met technische knoppen  
**Problem:** Geen snelle, begrijpelijke keuze snelheid ↔ kwaliteit  
**Impact:** Traag of onnauwkeurig dicteren; Advanced/Whisper blijft dicht  
**Desired outcome:** Eén klik naar een veilig startprofiel; handmatig bijsturen blijft mogelijk

## Goal

Drie presets die **model** (+ veilige beam/VAD-defaults) zetten, met korte
uitleg, expliciete gebruikerkeuze, en bestaande herstart-hint bij modelwissel.

## Non-goals

- Trial-opname / benchmark / hardware- of GPU-detectie
- `device` / `compute_type`
- Auto-apply zonder Opslaan
- Incremental STT / Meeting Buddy-knobs
- First-run modal wizard
- Wijzigen van prompt/hotwords/no_speech/condition_on_previous via preset

## Users and scenarios

1. Nieuwe gebruiker opent Instellingen → Geavanceerd → kiest **Snel** → Opslaan
   → (herstart indien model wijzigt) → dicteert sneller.
2. Gebruiker op trage laptop: **Snel**; op sterke machine: **Nauwkeurig**.
3. Power user past beam handmatig aan → preset wordt “Aangepast”; modelcombo blijft
   bruikbaar.

## Functional requirements

- **FR-01** Op tab Geavanceerd: sectie **Presets** met drie keuzes:
  `fast` / `balanced` / `accurate` (UI: Snel / Gebalanceerd / Nauwkeurig).
- **FR-02** Presetwaarden (alleen deze sleutels):

  | Id | model | whisper_beam_size | whisper_vad_filter | whisper_vad_min_silence_ms |
  |----|-------|-------------------|--------------------|----------------------------|
  | fast | base | 1 | true | 300 |
  | balanced | small | 5 | true | 300 |
  | accurate | medium | 5 | true | 300 |

- **FR-03** Kiezen van een preset vult direct de formuliervelden (model + Whisper-
  controls); Opslaan blijft vereist.
- **FR-04** Korte beschrijving per preset (i18n nl/en/de).
- **FR-05** Config mag `dictation_preset` bewaren (`fast`|`balanced`|`accurate`
  of leeg/afwezig = aangepast). Bij Opslaan: als velden exact een preset matchen
  → die id; anders leeg.
- **FR-06** Handmatige wijziging van model of de preset-gebonden Whisper-velden
  in de dialoog → selectie naar “aangepast” (geen radio geselecteerd / custom).
- **FR-07** Bestaande herstart-notitie bij modelwijziging blijft gelden.
- **FR-08** Prompt, hotwords, no_speech, condition_on_previous worden door
  presets **niet** overschreven.

## Quality requirements

- **QR-01** Geen focus-steal buiten het Instellingen-venster.
- **QR-02** Local-first; geen netwerk voor presets.
- **QR-03** Unit tests voor preset-tabel, match/normalize, en “custom” bij mismatch.
- **QR-04** i18n compleet (nl/en/de).

## Supported platforms

Windows primair; UI via bestaande PySide6-Instellingen (ook macOS/Linux runtime).

## Edge cases

- Onbekende `dictation_preset` in config → negeren (custom).
- Model buiten `KNOWN_MODELS` blijft via bestaande normalize → `small`.
- Preset wijzigt model terwijl Whisper-tab al open is in dezelfde dialoog →
  widgets synchroon.

## Privacy considerations

Geen audio, geen telemetrie, geen machine-fingerprint.

## Dependencies

Bestaande `config.whisper_settings_from_config` / model-normalize; geen ADR.

## Risks

- Gebruikers verwachten “magische” hardware-optimalisatie → copy moet duidelijk
  snelheid/kwaliteit zijn, geen systeemsmeting.
- `medium` download bij first choose accurate → bestaande splash/load-pad.

## Acceptance criteria

1. Given Instellingen Geavanceerd, When gebruiker kiest Snel, Then model=base en
   beam=1 in de velden (vóór Opslaan).
2. Given Opslaan na Gebalanceerd, Then config bevat model=small, beam=5,
   vad aan, `dictation_preset=balanced`.
3. Given matched preset, When gebruiker beam handmatig wijzigt en opslaat, Then
   `dictation_preset` leeg/afwezig.
4. Given modelwijziging via preset, When opslaan, Then bestaande herstart-notitie
   gedrag blijft.
5. Unit tests groen voor preset helpers.

## Required evidence

- `pytest` op config/preset-tests
- Handmatige smoke: drie presets → Opslaan → velden/config kloppen

## Agent ownership

| Rol | Agent |
|-----|--------|
| Responsible | `core-python-architect` |
| Consult | `audio-speech` (presetwaarden), `ux-product-design` (copy/plaatsing) |
| Review | `/code-review` vóór merge |

## Open questions

Geen — scope vast als thin slice.
