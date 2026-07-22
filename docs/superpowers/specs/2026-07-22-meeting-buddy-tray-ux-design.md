# Design — Meeting Buddy tray- & agenda-UX

- **Datum:** 2026-07-22
- **Status:** Review (spec geschreven; wacht op goedkeuring)
- **Branch (voorstel):** `feat/meeting-buddy-tray-ux`
- **Gerelateerd:**
  [2026-07-19-meeting-buddy-mvp-design.md](2026-07-19-meeting-buddy-mvp-design.md),
  [2026-07-19-modules-design.md](2026-07-19-modules-design.md),
  [2026-07-19-module-capabilities-design.md](2026-07-19-module-capabilities-design.md)

## Probleem

Na het inschakelen van Meeting Buddy is de volgende stap onduidelijk: het
Modules-venster toont vooral “ingeschakeld”, terwijl Start/Stop in de tray-root
staan en Agenda bewerken alleen in het Modules-venster. Agenda en
loopback/uitvoer zitten in één prep-dialoog. Agenda’s bestaan alleen in
geheugen; je kunt ze niet klaarzetten en later starten. Dialogen missen het
herkenbare microfoonicoon van de tray.

## Doel

Meeting Buddy voelt als één duidelijke plek in tray én Modules-venster, met
gescheiden **agenda** en **eigenschappen**, en met opslaan/laden van agenda’s
zonder meteen een meeting te starten.

## Beslissingen (vastgelegd met gebruiker)

| Onderwerp | Keuze |
|-----------|--------|
| Na module Opslaan | Modules-venster blijft open en toont actieknoppen |
| Agenda-opslag | Bibliotheek in app **én** Open bestand / Opslaan als |
| Meeting starten | Altijd eerst agenda-dialoog ter bevestiging |
| Aanpak | Cascade + gesplitste dialogen + agenda-bibliotheek |

## Scope

### In scope

- Tray: één cascade **Meeting Buddy ▸** (Start / Stop / Agenda bewerken /
  Eigenschappen); Start/Stop verdwijnen uit de tray-root
- Modules-venster: na Opslaan open houden; bij enabled Meeting Buddy dezelfde
  vier acties als knoppen
- Agenda-dialoog met titel, punten, bibliotheek, Open/Opslaan/Opslaan als
- Eigenschappen-dialoog: alleen loopback + uitvoerapparaat
- Startflow: bevestiging via agenda-dialoog; audio-prefs uit Eigenschappen
- Zelfde microfoonicoon (tray-silhouet) op relevante Tk-dialogen
- Locales, user help, modules-docs bijwerken

### Expliciet buiten scope

- Apart MeetingBuddy-hoofdvenster / workspace
- Cloud-sync van agenda’s
- Import uit Teams/Outlook-agenda
- Wijzigingen aan hint-engine of overlay-gedrag tijdens een lopende meeting

## Tray

```text
Tray
├─ … bestaande items …
├─ Meeting Buddy ▸
│  ├─ Meeting starten…
│  ├─ Meeting stoppen
│  ├─ Agenda bewerken
│  └─ Eigenschappen
└─ Modules…          (bestaand: enable/disable dialoog)
```

- Cascade is zichtbaar wanneer de module enabled/running is (na
  `_reload_modules` / `refresh_modules_menu`, zoals nu).
- Geen `in_tray_root` meer voor Start/Stop; alle Meeting Buddy-acties via
  module-cascade (`in_tray`) of Modules-dialoogknoppen.
- **Keuze:** een dedicated root-submenu **Meeting Buddy ▸** (niet begraven
  onder het generieke “Modules”-submenu), zodat Start/Stop/Agenda/Eigenschappen
  onder die ene herkenbare label hangen.

## Modules-venster

1. Gebruiker schakelt Meeting Buddy in → Opslaan.
2. `apply_settings` / `_reload_modules` / tray-refresh zoals nu.
3. Dialoog **blijft open**.
4. Onder de Meeting Buddy-rij (of in het actiegebied voor die module)
   verschijnen knoppen: Meeting starten…, Meeting stoppen, Agenda bewerken,
   Eigenschappen.
5. Geen aparte toast verplicht; de acties in hetzelfde scherm zijn de
   “wat nu?”-hint.

## Agenda-dialoog

### Inhoud

- **Titel** — verplicht om in de bibliotheek op te slaan
- **Agendapunten** — één onderwerp per regel (bestaande `parse_agenda`)
- **Bibliotheek** — lijst van opgeslagen agenda’s
- Bestandsacties: Openen (uit lijst), Opslaan, Opslaan als…, Open bestand…

### Opslag

- Standaardmap:
  `%APPDATA%\praatMaar\meeting-buddy\agendas\` (Windows; equivalent onder
  bestaande app-datamap op andere platforms)
- Bestandsformaat: UTF-8 plain text, extensie `.txt` of `.md`
  - Regel 1: `# <titel>` (Markdown H1); ontbreekt die regel, dan is de
    titel de bestandsnaam zonder extensie
  - Overige niet-lege regels (geen `#`-heading): agendapunten (één per regel)
- **Open bestand… / Opslaan als…** mogen buiten de bibliotheekmap

### Knoppen

| Context | Knoppen |
|---------|---------|
| Via “Meeting starten…” | Opslaan, **Meeting starten**, Annuleren/Sluiten |
| Via “Agenda bewerken” | Opslaan, Sluiten (geen verplichte start) |

### Validatie

- Bibliotheek-opslag: titel + minstens één agendapunt
- Meeting starten met lege agenda: **niet toegestaan**; focus op het
  puntenveld
- Annuleren/Sluiten start geen meeting

### Sessiegeheugen

- Laatst bevestigde/geladen agenda blijft in de orchestrator beschikbaar
  (huidig `_agenda_text`-gedrag), zodat heropenen de tekst toont
- Welke bibliotheek-entry “actief” is, mag in-process onthouden worden; hoeft
  niet persistent tot een latere iteratie

## Eigenschappen-dialoog

- Alleen:
  - Meetinggeluid opnemen (Windows loopback) — aan/uit
  - Uitvoer voor meetinggeluid — keuzelijst
- Opslaan → bestaande `save_meeting_buddy_preferences` /
  `meeting-buddy/config.json` (`enable_loopback`, `loopback_device`)
- Geen agenda in dit scherm
- macOS: zelfde dialoogstructuur; loopback-UI uitgeschakeld of duidelijk
  “niet beschikbaar” (geen valse belofte)

## Start- & stopflow

```text
Meeting starten…
    → Agenda-dialoog (bevestiging; evtl. laden/opslaan)
    → gebruiker kiest “Meeting starten”
    → loopback/device uit opgeslagen Eigenschappen
    → bestaande orchestrator.start + overlay (ongewijzigd gedrag)

Meeting stoppen
    → bestaande stop + overlay dicht
```

- Oude gecombineerde prep-dialoog (`show_meeting_prep_dialog` met agenda +
  loopback) verdwijnt; wordt vervangen door agenda-dialoog +
  eigenschappen-dialoog.
- “Meeting starten…” opent **altijd** eerst de agenda-dialoog, ook als er al
  een agenda in geheugen staat.

## Icoon

- Tray blijft het programmatische microfoonsilhouet (`tray._make_icon`).
- Tk-dialogen (Modules, Agenda, Eigenschappen, en bij voorkeur overige
  app-dialogen in dezelfde ronde als het praktisch is) zetten `iconphoto` /
  equivalent naar hetzelfde silhouet (gedeelde helper, geen veer/standaard-Tk
  als producticoon).

## Module-contract / acties

Nieuwe of herziene `ModuleAction`s voor Meeting Buddy:

| id | Label (nl) | Tray | Modules-knop |
|----|------------|------|--------------|
| `start_meeting` | Meeting starten… | cascade | ja |
| `stop_meeting` | Meeting stoppen | cascade | ja |
| `prepare_agenda` | Agenda bewerken | cascade | ja |
| `properties` | Eigenschappen | cascade | ja |

- `in_tray_root=False` voor alle vier; zichtbaar in de Meeting Buddy-cascade
  (`in_tray=True` of equivalent na eventuele tray-API-uitbreiding voor
  genaamde cascademenu’s).

## Tests (richting)

- Cascade/menu-entry: Start/Stop niet langer als tray-root-acties
- Modules-dialoog blijft open na apply wanneer gevraagd; actieknoppen voor
  enabled Meeting Buddy
- Agenda: opslaan/laden bibliotheek; Opslaan als / Open bestand
- Start geweigerd bij lege agenda; start na bevestiging gebruikt opgeslagen
  loopback-prefs
- Eigenschappen schrijven prefs zonder agenda te muteren

## Success criteria

1. Na inschakelen + Opslaan ziet de gebruiker meteen Start / Stop / Agenda /
   Eigenschappen zonder de tray opnieuw te hoeven “ontdekken”.
2. Tray toont één Meeting Buddy-cascade i.p.v. losse Start/Stop in de root.
3. Agenda kan opgeslagen en later geladen worden zonder meeting te starten.
4. Loopback/uitvoer zitten alleen onder Eigenschappen.
5. Dialogen tonen het microfoonicoon.

## Modules-venster: sluitgedrag

Na **Opslaan** blijft het Modules-venster **altijd** open (niet alleen voor
Meeting Buddy). Sluiten blijft expliciet via de venster-sluitknop / Annuleren.
