# Product specification — Whisper-opties in Instellingen

## Status

**Accepted** — 2026-08-08 (must-set uit inventory; implementatie direct)

## Problem

**User:** Dicteergebruiker die kwaliteit/snelheid of domeinwoorden wil bijsturen.  
**Situation:** Faster-Whisper-opties staan hardcoded in `Opnamesessie` / recovery.  
**Problem:** Geen UI om beam, VAD, prompt/hotwords of no-speech te wijzigen.  
**Desired outcome:** Eigen tab **Whisper** naast Algemeen / Taal / Geavanceerd.

## Goal

Exposeer de zinvolste `transcribe()`-opties live (zonder herstart), met defaults =
huidige hardcodes. Modelgrootte blijft op Geavanceerd (herstart).

## Non-goals

- `device` / `compute_type` (herstart + GPU)
- word timestamps, temperature-ladder, suppress-tokens, multilingual
- Meeting Buddy continuous STT (`speech_to_text` houdt eigen beam=1)
- Wijzigen van model-download / auth

## Functional requirements

- **FR-01** Tab Whisper met: beam_size, vad_filter, min_silence_ms,
  condition_on_previous_text, no_speech_threshold, initial_prompt, hotwords.
- **FR-02** Defaults: beam=5, vad=on, min_silence=300, condition=off,
  no_speech=0.6, prompt/hotwords leeg.
- **FR-03** Opslaan → config.json + live toepassen op volgende dicteer-/recovery-
  transcriptie (geen app-herstart).
- **FR-04** Ongeldige waarden veilig clampen/sanitizen.
- **FR-05** Zelfde kwargs voor dicteercyclus, chunk-pad en recovery-retranscribe.

## Acceptance criteria

1. Tab zichtbaar in Instellingen (nl/en/de).
2. Wijzig beam of VAD → volgende Shift+Esc gebruikt nieuwe waarden.
3. Lege prompt/hotwords → niet doorgeven aan Faster-Whisper.
4. Unit tests voor sanitize + kwargs.

## Agent ownership

| Rol | Agent |
|-----|--------|
| Responsible | `core-python-architect` |
| Consult | `audio-speech`, `ux-product-design` |
