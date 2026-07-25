# Designbrief — Instellingen (praatMaar)

## Product in één zin

**praatMaar** is een lokale dicteerapp. **Instellingen** is het centrale scherm voor
hoe je dicteert: microfoon, sneltoets, bedieningsmodus, talen, Whisper-model, en
beheer van **herstel-audio** — geopend via het systeemvak.

## Wat we zoeken

Vormgeving van het **Instellingen-venster** (tabs + footer Opslaan/Annuleren),
inclusief de **sneltoets-opname**-interactie en de **Herstel-audio**-sectie.
Functioneel bestaat het scherm al (Tk + tabs); dit is een redesign-brief.

Niet in scope van dit scherm (eigen briefs / tray-items):

- **Bestemmingen** ([destinations.md](destinations.md))
- **Modules** ([modules.md](modules.md)) / Meeting Buddy / Local LLM
- **Help**

Die mogen visueel familie zijn, maar horen **niet** als extra tabs in Instellingen.

## Rol van het scherm

| Doet | Doet niet |
|------|-----------|
| Globale dicteer-voorkeuren | Bestemmingen beheren |
| Sneltoets opnemen | Meeting Buddy / LLM-config |
| Model + talen kiezen | Live opname/status (dat is de pill) |
| Herstel-WAV’s beheren / opnieuw transcriberen | Cloud-accounts of sync |

**Platformnotitie:** op macOS opent Instellingen in een apart proces (stabiliteit);
design mag OS-native aanvoelen (Win/Mac), inhoud blijft gelijk.

## Informatie-architectuur (huidige tabs)

Titel: **praatMaar — Instellingen**

### Tab Algemeen

| Sectie | Controls |
|--------|----------|
| Microfoon | Combobox (systeemstandaard + apparaatlijst) |
| Positie van de indicator | Boven-midden / Onder-midden / Laatst gepositioneerd |
| Bediening | Toggle · Push-to-talk |
| Sneltoets | Weergave combo · knop **Opnemen…** → luistermodus |
| Opties | Autostart · Automatisch plakken (alleen zonder actieve bestemming) · Microfoon warm houden |

### Tab Taal

| Sectie | Controls |
|--------|----------|
| Spraakherkenning | nl / en / de (Whisper) |
| Interfacetaal | Nederlands / English / Deutsch |

**Belangrijk:** twee aparte talen — UI ≠ spraak. Design moet dat onderscheid
duidelijk maken (korte helpertekst).

### Tab Geavanceerd

| Sectie | Controls |
|--------|----------|
| Whisper-model | base / small / medium + hint: wijziging pas na herstart |
| Herstel-audio | Lijst WAV’s · empty state · status · Map openen · Verwijderen · Alles wissen · Opnieuw transcriberen |

## Interacties om mee te ontwerpen

### Sneltoets opnemen

1. Gebruiker klikt **Opnemen…**
2. UI toont “Druk de combinatie in…” (luistermodus)
3. Combinatie verschijnt live; bevestigen met **Gebruik deze**
4. Alleen modifiers → fout/hint: voeg minstens één gewone toets toe

Dit is de meest “speciale” control — verdient een duidelijk **listening**-state.

### Herstel-audio

- Lijst van mislukte opnames.
- Selectie → Verwijderen / Opnieuw transcriberen.
- Bezig: “Bezig met transcriberen…”
- Na succes: vraag of WAV verwijderd mag worden.
- Bevestigingen bij wissen (één / alles).

### Opslaan / Annuleren

- Footer over alle tabs heen.
- Modelwijziging mag na opslaan een herstart-notitie tonen.

## Designprincipes

1. **Instellingen = rustig beheer** — geen HUD/waveform-esthetiek van de pill.
2. **Primair vs. geavanceerd** — Algemeen/Taal dagelijks; model + herstel minder vaak.
3. **Scannable secties** — duidelijke headings, verticale ritme.
4. **Twee talen uitleggen** — Spraak vs. Interface.
5. **Plakken-hierarchie** — globale auto-plakken alleen zonder actieve bestemming;
   hint naar Bestemmingen is welkom.
6. **Familie** — zelfde merktaal als Bestemmingen, pill, Modules, Meeting Buddy.
7. **i18n** — ruimte voor DE/EN; platform-aware labels (Windows/macOS meestarten).
8. **Toegankelijk** — focusvolgorde tabs → velden → Opslaan.

## Frames (minimaal)

1. Algemeen — alle secties, normale staat
2. Sneltoets luisteren — Opnemen… actief
3. Taal — beide comboboxen + korte uitleg
4. Geavanceerd — model + herstel met 2–3 bestanden
5. Herstel leeg
6. Herstel bezig
7. Optioneel: fout sneltoets (alleen modifiers)

## Merk & tone

- Titel: **praatMaar — Instellingen**.
- Tone: helder, kort; modelnamen mogen technisch blijven met menselijke herstart-hint.
- Geen cloud-/account-UI.

## Leveringen

- Figma/PDF: drie tabs + sneltoets-state + herstel-states.
- Componenten: tab bar, section header, combobox, checkbox row, hotkey capture,
  list row (recovery), footer buttons, helper/warning text.
- Suggestie breedte/hoogte dialoog.

## Wat níet

- Bestemmingen, Modules, Help of Meeting Buddy in dit venster.
- Account, sync, thema-winkel, plugin-store.
- Meer dan nodig categorieën — drie tabs volstaan tenzij herstructurering duidelijker is.

## Relatie tot andere briefs

| | Instellingen | Bestemmingen | Pill | Modules |
|--|--------------|--------------|------|---------|
| Rol | Hoe je dicteert | Waar transcripts naartoe | Live status | Extensies aan/uit |
| Moment | Af en toe | Af en toe | Continu | Af en toe |
| Vorm | Tabbed dialoog | Lijst-dialoog | Capsule HUD | Module-kaarten |
