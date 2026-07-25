# Designbrief — Bestemmingen (praatMaar)

## Product in één zin

**praatMaar** dicteert lokaal en slaat transcripts op schijf op. **Bestemmingen**
laten je via **spraak** wisselen waar die tekst naartoe gaat: elke bestemming is
een **naam + map** (plus opties). De actieve bestemming is **sticky** tot je
wisselt of terugzet naar standaard.

## Wat we zoeken

Vormgeving voor het **Bestemmingen-beheerscherm** (tray → Bestemmingen) en de
**toevoegen/wijzigen**-subdialoog. Optioneel: consistentie met de **pill**
([pill.md](pill.md)) voor map-/actief-iconografie — geen pill-redesign hier.

Dit is een **beheer-UI** (lijst + form), geen live HUD.

## Kernconcept

| Begrip | Betekenis |
|--------|-----------|
| Bestemming | Naam + map (+ plakken + opslagmodus) |
| Sticky | Actieve bestemming blijft tot wissel/reset |
| Standaard | Altijd aanwezig; app-opslagmap; niet bewerkbaar/verwijderbaar |
| Spraakwissel | Korte opname met **exacte** naam → actief; `standaard` / `default` / `standard` → reset |
| Pill | Toont actieve naam in idle |

**Privacy:** transcripts zijn platte tekstbestanden. UI mag subtiel waarschuwen
voor gedeelde/onveilige mappen — niet moraliserend.

## Oppervlakken

### 1. Hoofddialoog — Bestemmingen

Titel: **praatMaar — Bestemmingen**

| Zone | Inhoud |
|------|--------|
| Intro | Korte uitleg: spraakwissel + reset-woorden (nu één lange alinea — graag scannable) |
| Lijst | Rijen: Standaard + eigen bestemmingen |
| Acties | Toevoegen · Wijzigen · Verwijderen · Actief zetten |
| Map openen | Standaard opslagmap · Actieve map |
| Footer | Annuleren · Opslaan |

**Kolommen:**

| Kolom | Inhoud |
|-------|--------|
| Naam | Weergavenaam (= spraakopdracht) |
| Map | Pad of “App-opslagmap” bij Standaard |
| Plakken | Ja / Nee |
| Opslag | Nieuw / Toevoegen |
| Actief | ✓ op de actieve rij |

**Gedrag:**

- Rij **Standaard** altijd zichtbaar; geen bewerken/verwijderen; wél actief maken.
- Empty state + CTA Toevoegen.
- Opslaan past lijst + actieve keuze toe; Annuleren verwerpt lokale edits.

### 2. Subdialoog — Toevoegen / Wijzigen

1. **Naam** (verplicht; uniek; niet gereserveerde reset-woorden)
2. **Map** + Bladeren…
3. **Automatisch plakken**
4. **Opslag:** nieuw bestand per opname **of** toevoegen aan bestaand bestand
   (+ bestandskeuze)

Validatiefouten: naam/map/append verplicht, duplicaat, gereserveerde naam,
naambotsing.

### 3. Touchpoints buiten dit scherm

- **Tray:** Bestemmingen (naast Instellingen, Modules, Help).
- **Pill idle:** map-icoon + naam.
- **Niet** in algemene Instellingen (bewuste scheiding).

## Designprincipes

1. **Beheer ≠ live** — rustig dialoogvenster.
2. **Standaard is heilig** — visueel locked/system row.
3. **Actief is één blik** — duidelijke indicator.
4. **Spraak eerst** — de **naam** is de stemopdracht; moedig korte unieke namen aan.
5. **Familie** — zelfde merktaal als pill / Instellingen / Modules.
6. **i18n** — ruimte voor langere Duitse labels.
7. **Toegankelijk** — voldoende rijhoogte, contrast, focus-states.

## Frames (minimaal)

1. Leeg — alleen Standaard + empty state
2. Gevuld — 3–5 bestemmingen, één actief
3. Selectie Standaard — Wijzigen/Verwijderen disabled
4. Toevoegen — “nieuw bestand”
5. Wijzigen — “toevoegen aan bestand” met bestandsveld
6. Fout — duplicaat of gereserveerde naam

## Merk & tone

- Titel: **praatMaar — Bestemmingen**.
- Tone: helder, kort; “sticky” niet in UI-copy.
- Iconen: map, lock voor Standaard, check voor actief — consistent met pill-map.

## Leveringen

- Figma/PDF: hoofddialoog + subdialoog (states hierboven).
- Componenten: list row (default / custom / active / selected), buttons, form
  fields, empty state.
- Keuze tabel vs. card-list — motiveer kort.

## Wat níet

- Cloud-sync of team-bestemmingen.
- Fuzzy spraakmatch.
- Bestemmingen in Instellingen-tabs.
- Meeting Buddy transcriptmap hier (zit in Meeting Buddy-eigenschappen).

## Relatie tot andere briefs

| | Bestemmingen | Pill | Meeting Buddy |
|--|--------------|------|---------------|
| Rol | Beheer waar dicteer-transcripts naartoe | Live status + actieve naam | Vergader-overlay |
| Moment | Af en toe | Continu | Tijdens meeting |
| Vorm | Dialoog / lijst | Capsule | Overlay-paneel |
