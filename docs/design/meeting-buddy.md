# Designbrief — Meeting Buddy (praatMaar)

## Product in één zin

**praatMaar** is een lokale Windows-dicteerapp (privacy: geen cloud). **Meeting Buddy**
is een experimentele module die tijdens een vergadering meeluistert en een compacte
**overlay** toont met agenda-voortgang, eventuele live samenvatting, vragen van
anderen, en korte hints — zonder het transcript zelf in beeld.

## Wat we zoeken

Een **vormgeving / UI-design** voor de Meeting Buddy-ervaring, met focus op de
**live overlay** (primair) en secondair de **agenda-** en **eigenschappen-dialogen**.
Geen volledige app-redesign van praatMaar; wel iets dat bij een serieuze, rustige
desktop-tool past (vergaderen, niet “dashboard”).

Doel: een ontwerp dat we later kunnen nabouwen (nu is alles functioneel Tk/ttk-placeholder).

Entrypoints (Modules + tray) staan in [modules.md](modules.md); dit brief focust
op de **live** en **prep**-UI van Meeting Buddy zelf.

## Gebruiker & moment

- Host of deelnemer in Teams/Zoom-achtige calls op Windows.
- Overlay staat **bovenop andere apps**, rechtsboven, **zonder focus te stelen**.
- Gebruiker kijkt vooral naar de meeting; Meeting Buddy is **perifere hulp**.
- Taal UI: NL (primair), ook EN/DE — houd teksten kort, ruimte voor vertaling.

## Oppervlakken om te ontwerpen

### 1. Live overlay (hoofdlevering)

Altijd-bovenop, compact, niet-resizebaar in MVP. **Geen transcriptweergave.**

| Zone | Inhoud | Gedrag |
|------|--------|--------|
| Header | Statusdot · korte statusregel · timer `HH:MM:SS` · Minimaliseren / Stoppen | Dot pulseert rood bij actieve opname |
| Opnamebanner (conditioneel) | Mic only / mic+meetinggeluid / herverbinden / fout / “transcriptie loopt achter” | Alleen tonen als relevant |
| Agenda | Lijst agendapunten met statusladder | Compacte regels |
| Samenvatting (optioneel) | Live samenvatting of placeholder “volgt zodra…” | Alleen als Local LLM + optie aan |
| Vragen van anderen | Open vragen, max. ~5, prefix `?` | Alleen tonen als er vragen zijn |
| Hints | Max. **3** hintkaarten; één “emphasis” | Negeren / soms Bevestigen |
| Footer | Opname · Transcriptie status | Subtiel; herverbind bij mic-fout |

**Agenda-statusladder:**

| Status | Betekenis | Nu (tekst) |
|--------|-----------|------------|
| open | Nog niet behandeld | ○ |
| treated | Substantieel besproken | ◐ |
| sequential | Op volgorde “afgewerkt” | ● |
| confirmed | Bevestigd na herbespreking | ✓ |

Ontwerp graag **iconografie of typografie** die deze ladder in één oogopslag
leesbaar maakt (kleur + vorm; toegankelijk, niet alleen kleur).

**Hintkaarten:** korte tekst; acties Negeren / soms Bevestigen; één kaart emphasized.

### 2. Agenda-dialoog (vóór/naast start)

- Agenda als regels (één onderwerp per regel).
- Bibliotheek: **Recent** + **Alle agenda’s** (`.md`).
- Acties: Openen, Opslaan, Opslaan als, Meeting starten, Sluiten/Annuleren.
- Mag leeg starten (zonder agenda).

### 3. Eigenschappen-dialoog

- Meetinggeluid (Windows loopback) aan/uit + uitvoerapparaat.
- Map voor meeting-transcripts.
- Live samenvatting (Local LLM) aan/uit + drempels (seconden / tekens).
  Standaard **uit**; aanzetten via deze dialoog na klaar Local LLM.

### 4. Entrypoints (licht meenemen)

Tray **Meeting Buddy ▸** en Modules-actieknoppen: starten… / starten (snel) /
stoppen / agenda / eigenschappen. Overlay-branding mag aansluiten op
praatMaar-microfoon-silhouet.

## Designprincipes

1. **Één blik:** luistert de tool? waar staan we in de agenda? is er iets te doen?
2. **Compact:** breedte ~320–380px; hoogte groeit met inhoud maar blijft zijpaneel.
3. **Geen transcript-UI** in de overlay.
4. **Kalm maar alert:** rustige default; rood/oranje alleen voor opname/fout/vertraging.
5. **Hint ≠ alarm:** max. 3 hints.
6. **Desktop-native:** Windows 11-gevoel; geen speelse consumer-app of paarse AI-cliché.

## States / mockups (minimaal)

1. Idle / starten — mic start, nog geen hints
2. Actief + loopback — mic + meetinggeluid, agenda half gevuld
3. Actief + live samenvatting + vragen — “rijke” overlay
4. Hints met emphasis — 2–3 kaarten
5. Fout / mic-probleem — banner + herverbind
6. Transcriptie loopt achter — subtiele waarschuwing
7. Agenda-dialoog en Eigenschappen (één frame elk)

## Merk & tone

- Overlay-titel: **praatMaar — Meeting Buddy**.
- Tone: zakelijk, behulpzaam, Nederlands kort.
- Privacy: lokaal — subtiel in dialogen, niet schreeuwen in de overlay.
- Badge **Experimenteel** welkom op entrypoints (zie ook [modules.md](modules.md)).

## Leveringen

- Desktop-mockups (Figma of PDF) van overlay + 2 dialogen.
- Componenten: statusdot, agenda-rij, hintkaart, banner, knoppenhiërarchie.
- Kleurenpalet + typografie.
- Korte toelichting per state.
- Optioneel: light/dark — light voldoende voor MVP.

## Wat níet

- Apart Meeting Buddy-hoofdvenster / workspace.
- Chat-achtige transcriptviewer in de overlay.
- Cloud-sync / Teams-import UI.
- Volledige praatMaar Instellingen-herontwerp.

## Huidige placeholder (referentie, niet als stijl)

Lichtgrijs `#F4F7FA`, tekst `#15334A`, hint-emphasis `#DCEEFF`, opnamebanner
`#FFEBEE` / rood. Functioneel, niet “designed”. Mag volledig vervangen worden
zolang de **informatie-architectuur** intact blijft.

## Relatie tot andere briefs

| | Meeting Buddy | Pill | Modules |
|--|---------------|------|---------|
| Moment | Vergadering (lang) | Dicteren (kort) | Enable + startacties |
| Inhoud | Agenda, hints, summary, vragen | Status + waveform + bestemming | Kaarten + toggles |
| Formaat | Overlay-paneel | Capsule ~340×60 | Dialoog |
