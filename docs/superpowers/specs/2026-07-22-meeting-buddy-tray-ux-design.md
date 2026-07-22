# Design — Meeting Buddy tray- & agenda-UX

- **Datum:** 2026-07-22
- **Status:** Review (herzien na feedback; wacht op goedkeuring)
- **Branch:** `feat/meeting-buddy-tray-ux`
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
zonder meteen een meeting te starten — inclusief een snelle startroute voor
terugkerende meetings.

## Beslissingen (vastgelegd met gebruiker)

| Onderwerp | Keuze |
|-----------|--------|
| Na module Opslaan | Modules-venster blijft **altijd** open (alle modules) |
| Agenda-opslag | Bibliotheek in app **én** Open bestand / Opslaan als |
| Bestandsformaat (MVP) | Alleen `.md` |
| Titel | Afgeleid van bestandsnaam (zoals Word); geen apart verplicht titelveld |
| Meeting starten | Agenda-dialoog ter bevestiging |
| Snelle start | Modifier+Start (Shift) → direct starten met huidige agenda |
| Bibliotheek-UI | Sectie **Recent** boven **Alle agenda’s** |
| Aanpak | Cascade + gesplitste dialogen + agenda-bibliotheek |

## Scope

### In scope

- Tray: één cascade **Meeting Buddy ▸** (Start / Stop / Agenda bewerken /
  Eigenschappen); Start/Stop verdwijnen uit de tray-root
- Modules-venster: na Opslaan **altijd** open houden; bij enabled Meeting Buddy
  dezelfde vier acties als knoppen
- Agenda-dialoog: punten, bibliotheek (Recent + Alle), Open/Opslaan/Opslaan als
  (`.md`)
- Eigenschappen-dialoog: alleen loopback + uitvoerapparaat
- Twee startroutes: bevestigen via agenda **of** Shift+Start direct
- Zelfde microfoonicoon (tray-silhouet) op relevante Tk-dialogen
- Locales, user help, modules-docs bijwerken

### Expliciet buiten scope

- Apart MeetingBuddy-hoofdvenster / workspace
- Cloud-sync van agenda’s
- Import uit Teams/Outlook-agenda
- Instelling “Altijd agenda tonen” (later; MVP gebruikt Shift+Start)
- Rijke Markdown-parsing (lijsten `-`/`*` e.d.) — formaat `.md` is gekozen
  zodat dat later kan; MVP behandelt inhoud als regels/onderwerpen
- Wijzigingen aan hint-engine of overlay-gedrag tijdens een lopende meeting

## Tray

```text
Tray
├─ … bestaande items …
├─ Meeting Buddy ▸
│  ├─ Meeting starten…          (opent agenda-bevestiging)
│  ├─ Meeting starten (snel)    (Shift-route — zie Startflow)
│  ├─ Meeting stoppen
│  ├─ Agenda bewerken
│  └─ Eigenschappen
└─ Modules…          (bestaand: enable/disable dialoog)
```

- Cascade is zichtbaar wanneer de module enabled/running is (na
  `_reload_modules` / `refresh_modules_menu`, zoals nu).
- Geen `in_tray_root` meer voor Start/Stop.
- **Keuze:** dedicated root-submenu **Meeting Buddy ▸** (niet begraven onder
  het generieke “Modules”-submenu).

### Shift+Start en pystray

Pystray ondersteunt niet overal modifier+klik op menuitems. MVP-keuze:

1. **Primair:** apart cascade-item **Meeting starten (snel)** naast
   **Meeting starten…**
2. **Aanvullend waar mogelijk:** Shift vastgehouden bij activeren van
   “Meeting starten…” →zelfde snelle pad (nice-to-have; niet blocker)

Documenteer beide labels in help/locales. Latere optie: voorkeursinstelling
“Altijd agenda tonen” i.p.v. of naast het snelle item.

## Modules-venster

1. Gebruiker wijzigt modules → Opslaan.
2. `apply_settings` / `_reload_modules` / tray-refresh zoals nu.
3. Dialoog **blijft altijd open** (alle modules, geen Meeting Buddy-uitzondering).
4. Onder de Meeting Buddy-rij verschijnen knoppen: Meeting starten…,
   Meeting starten (snel), Meeting stoppen, Agenda bewerken, Eigenschappen.
5. Geen aparte toast verplicht; de acties in hetzelfde scherm zijn de
   “wat nu?”-hint.

Sluiten blijft expliciet via venster-sluitknop / Annuleren.

## Agenda-dialoog

### Inhoud

- **Agendapunten** — één onderwerp per regel (bestaande `parse_agenda`;
  Markdown-lijsten later)
- **Geen verplicht titelveld** — titel = bestandsnaam zonder `.md`
  (bijv. `Budgetoverleg.md` → “Budgetoverleg”), zoals Word
- Optioneel: bestandsnaam tonen/bewerken bij **Opslaan als…** (save-dialog),
  niet als apart formulierveld bij elke edit
- **Bibliotheek** in twee secties:
  1. **Recent** — laatst gebruikte agenda’s (openen, starten, of opslaan
     telt als gebruik), max. ~5–8 items
  2. **Alle agenda’s** — volledige bibliotheekmap
- Bestandsacties: Openen (uit lijst), Opslaan, Opslaan als…, Open bestand…

### Opslag

- Standaardmap:
  `%APPDATA%\praatMaar\meeting-buddy\agendas\` (Windows; equivalent onder
  bestaande app-datamap op andere platforms)
- **MVP-formaat: alleen `.md`** (UTF-8)
  - Optioneel regel 1: `# <titel>` — als aanwezig, mag de UI die als
    weergavenaam gebruiken; ontbreekt die, dan bestandsnaam zonder extensie
  - Bij **Opslaan** naar een nieuw bestand zonder gekozen naam: afleiden van
    eerste agendapunt of `agenda-YYYYMMDD.md` (implementatie kiest één
    eenvoudige default; Opslaan als… blijft beschikbaar)
  - Overige niet-lege contentregels: agendapunten (MVP: plain lines)
- **Open bestand… / Opslaan als…** mogen buiten de bibliotheekmap; filter
  `.md`
- Recent-lijst: paden + timestamps in
  `meeting-buddy/config.json` (of klein `recents.json` ernaast)

### Knoppen

| Context | Knoppen |
|---------|---------|
| Via “Meeting starten…” | Opslaan, **Meeting starten**, Annuleren/Sluiten |
| Via “Agenda bewerken” | Opslaan, Sluiten (geen verplichte start) |

### Validatie

- Opslaan: minstens één agendapunt (bestandsnaam via dialoog of default)
- Meeting starten met lege agenda: **niet toegestaan**; focus op het
  puntenveld
- Snelle start met lege agenda: zelfde weigering + open agenda-dialoog of
  foutmelding
- Annuleren/Sluiten start geen meeting

### Sessiegeheugen

- Laatst bevestigde/geladen agenda blijft in de orchestrator beschikbaar
  (`_agenda_text`)
- Actief bestandspad + recent-lijst zijn persistent genoeg voor “elke
  maandag MT-overleg” (recent + snelle start)

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
    → Agenda-dialoog (bevestiging; Recent / laden / opslaan)
    → gebruiker kiest “Meeting starten”
    → markeer agenda als recent
    → loopback/device uit opgeslagen Eigenschappen
    → orchestrator.start + overlay

Meeting starten (snel)  [Shift-route]
    → géén agenda-dialoog
    → gebruik huidige sessie-agenda (laatst geladen/bevestigd)
    → zo leeg: weigeren en agenda-dialoog openen (of duidelijke melding)
    → anders: start met Eigenschappen-prefs + markeer recent

Meeting stoppen
    → bestaande stop + overlay dicht
```

- Oude gecombineerde prep-dialoog verdwijnt; agenda- en
  eigenschappen-dialoog gescheiden.
- Latere uitbreiding (buiten MVP): voorkeur “Altijd agenda tonen” die het
  snelle pad kan dempen of omdraaien.

## Icoon

- Tray blijft het programmatische microfoonsilhouet (`tray._make_icon`).
- Tk-dialogen (Modules, Agenda, Eigenschappen, en bij voorkeur overige
  app-dialogen in dezelfde ronde als het praktisch is) zetten `iconphoto` /
  equivalent naar hetzelfde silhouet (gedeelde helper).

## Module-contract / acties

| id | Label (nl) | Tray | Modules-knop |
|----|------------|------|--------------|
| `start_meeting` | Meeting starten… | cascade | ja |
| `start_meeting_quick` | Meeting starten (snel) | cascade | ja |
| `stop_meeting` | Meeting stoppen | cascade | ja |
| `prepare_agenda` | Agenda bewerken | cascade | ja |
| `properties` | Eigenschappen | cascade | ja |

- `in_tray_root=False` voor alle; zichtbaar in de Meeting Buddy-cascade.

## Tests (richting)

- Cascade: Start/Stop niet langer tray-root; wel Meeting Buddy-submenu
- Modules-dialoog blijft open na Opslaan (ongeacht welke module)
- Agenda: `.md` opslaan/laden; Recent boven Alle; Opslaan als / Open bestand
- Geen verplicht titelveld; weergavenaam uit bestandsnaam (of `#`-regel)
- Bevestigde start vs. snelle start; snelle start met lege agenda geweigerd
- Eigenschappen schrijven prefs zonder agenda te muteren

## Success criteria

1. Na inschakelen + Opslaan ziet de gebruiker meteen de Meeting Buddy-acties
   zonder de tray opnieuw te moeten “ontdekken”.
2. Tray toont één Meeting Buddy-cascade i.p.v. losse Start/Stop in de root.
3. Agenda kan als `.md` opgeslagen/geladen worden zonder meeting te starten;
   Recent staat bovenaan.
4. Terugkerende meetings: snelle start zonder extra bevestigingsscherm.
5. Loopback/uitvoer zitten alleen onder Eigenschappen.
6. Dialogen tonen het microfoonicoon.
