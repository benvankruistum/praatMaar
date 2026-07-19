# Design — Herstel-audio UI (Instellingen)

- **Datum:** 2026-07-19
- **Status:** Goedgekeurd (chat)

## Doel

Recovery-WAV’s (mislukte transcripties onder `%APPDATA%\praatMaar\recovery\`)
beheren én opnieuw laten transcriberen — vanuit een **sectie in Instellingen**.

## Gedrag

### Beheer

- Lijst van `.wav`-bestanden in `recovery_dir()`, nieuwste eerst.
- Weergave: bestandsnaam (timestamp) + grootte (en optioneel duur als goedkoop
  te bepalen; anders weglaten in v1).
- Acties:
  - **Map openen** → Verkenner op `recovery\`
  - **Verwijderen** (selectie) — met bevestiging
  - **Alles wissen** — met bevestiging
- Lege map: korte uitleg (“Geen herstel-opnames”).

### Opnieuw transcriberen

- Vereist selectie van één WAV.
- Gebruikt het **geladen** Whisper-model en huidige `speech_language`
  (zelfde als live dicteren).
- UI: knop disabled + statusregel “Bezig…” tijdens verwerking (achtergrondthread;
  dialoog blijft responsive).
- Bij succes:
  - transcript naar klembord + auto-plakken volgens huidige `auto_paste`-setting
    (zelfde pad als een normale dicteercyclus, of een gedeelde helper);
  - daarna **vraag**: “Opname verwijderen?” → Ja verwijdert de WAV, Nee bewaart.
- Bij falen: foutmelding in dialoog; WAV blijft staan.

### Interactie met dicteren

- Opnieuw-transcriberen weigeren (of in de wachtrij zetten) als er al een
  opname/verwerking loopt (`session.is_recording` / `is_processing`) — v1:
  **weigeren** met korte melding.

## UI

- Sectie **“Herstel-audio”** in `settings.py` (onderaan, na bestaande opties).
- i18n-keys nl/en/de.
- Geen nieuw tray-item.

## Techniek (richting)

- Lijst/wissen: uitbreidingen op `recovery.py` (`list_recovery_wavs`,
  `delete_recovery_file`, …) — puur stdlib, testbaar.
- Opnieuw-transcriberen: injecteerbare callback vanuit `dictation.py`
  (heeft `model` + paste-seams), niet Whisper importeren in `settings.py`.

## Buiten scope (v1)

- Afspelen in de app
- Auto-prune van recovery-map
- Recovery-WAV’s naar bestemmingsmappen verplaatsen
- Batch opnieuw-transcriberen

## Risico’s

- Lange WAV’s houden dialoog “bezig”; gebruiker moet wachten of dialoog sluiten
  annuleren (v1: sluiten tijdens bezig = annuleer niet mid-transcribe, wel
  knoppen disabled tot klaar — of cancel-flag later).
- Schijfruimte: zonder auto-prune blijft handmatig wissen nodig (UI dekt dat).
