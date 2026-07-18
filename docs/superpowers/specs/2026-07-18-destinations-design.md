# Design — bestemmingen (sticky) + transcriptmap-link

- **Datum:** 2026-07-18
- **Status:** Goedgekeurd (chat)

## Doel

1. Vanuit Instellingen eenvoudig de (default) transcriptmap openen.
2. Genoemde **bestemmingen** (naam + map): sticky actieve bestemming,
   zichtbaar in de pill; wisselen met stem via een take die *alleen* die naam is.

Geen aparte hotkeys. Namen zijn vrij (“boodschappenlijst”, “notities”, “project X”).

## Config

```json
"destinations": [
  { "name": "boodschappenlijst", "path": "D:/notes/boodschappen" },
  { "name": "notities", "path": "D:/notes" }
],
"active_destination": null
```

- `active_destination`: `null` = defaultmap (`%APPDATA%\praatMaar\transcripts\`),
  anders de `name` van een item in `destinations`.
- Ontbrekende keys = lege lijst + `null`.

## Gedrag

### Opslaan

- Geslaagd transcript → bestand in de map van de actieve bestemming, of default.
- Retentie/prune: zoals nu voor de defaultmap; projectmappen: geen auto-prune in v1
  (of alleen in default — expliciet: **prune alleen defaultmap**).

### Stem-wisseling (exacte match)

1. Normaliseer transcript: trim, lowercase, leestekens/whitespace vereenvoudigen.
2. Als genormaliseerde tekst **exact** gelijk is aan genormaliseerde `name` van een
   bestemming → zet `active_destination`, update pill, **niet plakken**, geen
   “inhoud”-transcript bewaren (of alleen een korte logregel).
3. Speciale reset-naam: **`standaard`** (vaste built-in, niet in de lijst nodig)
   → `active_destination = null`.
4. Geen match → normale dicteerflow (plakken + opslaan in actieve map).

### Pill

- Toont de actieve bestemmingsnaam (compact), of niets / subtiel “standaard” als `null`.
- Blijft zichtbaar in idle (niet alleen tijdens opname), zodat sticky duidelijk is.

### Instellingen / tray

- **Tray-menu** (naast elkaar): **Instellingen** | **Bestemmingen** | **Help** | Afsluiten.
- Bestemmingen-beheer is een **eigen dialoog** (niet begraven in Instellingen):
  - lijst naam + map (browse);
  - toevoegen / wijzigen / verwijderen;
  - actieve bestemming kiezen of wissen (naar standaard);
  - knop **Transcriptmap openen** (defaultmap);
  - knop **Actieve map openen** als er een bestemming actief is.
- Algemene Instellingen blijven voor mic, hotkey, talen, enz. (geen bestemmingenlijst daar).

### Help (gebruikersdocumentatie)

- **Tray-menu:** items **Instellingen**, **Bestemmingen**, **Help** (naast elkaar), daarna Afsluiten.
- Help opent een eenvoudig venster met:
  - wat bestemmingen zijn en hoe sticky + pill werken;
  - hoe je wisselt met stem (exacte match) en reset met **standaard**;
  - waar bestanden landen (default vs bestemming);
  - **risico’s:** Whisper-mishoren (geen match = veilig), te generieke namen
    (per ongeluk wisselen), transcripts onversleuteld op schijf.
- Teksten via i18n / `locales` of een `docs/user/`-bestand per taal — v1:
  liever **i18n-keys of één markdown per taal** zodat NL/EN/DE meegaan.
- Geen aparte website; alles lokaal.

## UI / i18n

Nieuwe keys voor labels (nl/en/de), inclusief Help-teksten. Geen nieuwe hotkeys.

## Buiten scope (v1)

- Fuzzy match / “begint met”
- Extra hotkey of PTT-variant voor commando’s
- Auto-prune in bestemmingsmappen
- Cloud-sync van bestemmingen
- Audio/recovery altijd meeverhuizen naar bestemmingsmap (recovery blijft in appdata)

## Risico’s

- Whisper hoort de naam verkeerd → geen match (veilig: blijft oude bestemming).
- Te korte/generieke namen → per ongeluk wisselen; documenteer korte unieke namen.
