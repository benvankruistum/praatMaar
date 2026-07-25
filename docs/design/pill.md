# Designbrief — Status-pill (praatMaar)

## Product in één zin

**praatMaar** is een lokale dicteertool. De **pill** is de kleine, altijd-zichtbare
statuscapsule die laat zien of de app **idle**, **opneemt**, **transcribeert**, of
een **fout/annulering** toont — zonder de focus te stelen van het veld waarin je typt.

## Wat we zoeken

Een **vormgeving van de pill** (desktop HUD): vorm, typografie, kleur, iconografie
en micro-interacties. Functioneel bestaat de pill al (Windows + macOS); dit is een
redesign-brief, geen greenfield.

Houd rekening met de aparte **Meeting Buddy-overlay** ([meeting-buddy.md](meeting-buddy.md)):
de pill is voor **dicteren**; Meeting Buddy is voor **vergaderen**. Ze kunnen tegelijk
op het scherm staan en moeten visueel familie zijn, maar niet hetzelfde component.

## Rol van de pill

| Doet | Doet niet |
|------|-----------|
| Toont dicteerstatus in één blik | Geen transcript tonen |
| Start/stop via knop (zelfde regels als sneltoets) | Geen Instellingen-UI |
| Toont sticky **bestemming** in idle | Geen lange berichten |
| Sleepbaar; positie onthouden | Geen focus stelen (typen blijft in het actieve veld) |

**Kritische UX-eis:** venster is *non-activating* — klikken op de pill mag
Word/Teams/browser **niet** de focus afpakken.

## Formaat & plaatsing

- Afmeting nu: ca. **340 × 60 px** (mag iets wijzigen, blijft “capsule”, geen paneel).
- Semi-transparant (~92% opacity).
- Posities: boven-midden / onder-midden / laatst gesleept.
- Sleepbaar; rechtsklik → contextmenu (tray-equivalent).

## Layout per toestand

### A. Idle — zonder bestemming

Pill **verborgen** (of minimaal). Gebruiker dicteert via sneltoets; tray blijft beschikbaar.

### B. Idle — met sticky bestemming (zichtbaar)

`[ map-icoon ]  Bestemmingsnaam (max ~24 tekens)     [ ● start ]  [ × ]`

- Map-icoon = “hier gaan transcripts naartoe”.
- **●** start opname (toggle of begin push-to-talk).
- **×** verbergt de idle-pill (bestemming blijft actief; pill komt terug bij
  volgende opname/bestemmingswissel).

### C. Opname

`[ pulserende rode dot ]  Opname   [ waveform ]   [ modus-tag ]  [ ■ stop ]`

- Waveform: ~18 staafjes, reageert op microfoonniveau.
- Modus-tag: `↔ toggle` | `● ptt` | `● meeting`.
- Dot pulseert tijdens opname.

### D. Transcriberen

`[ oranje dot ]  Transcriberen 45%   [ marching dots … ]   [ modus-tag ]`

- Voortgang 0–99% tijdens lokale Whisper-run; geen stopknop op de pill in deze fase.

### E. Geannuleerd / Fout (tijdelijk)

- **Geannuleerd** (~2 s): gedempte kleur, label “Geannuleerd”.
- **Mislukt** (~4 s): foutkleur, label “Mislukt”.
- Daarna terug naar idle (met of zonder bestemmingspill).

## Toestanden & kleuren (huidige placeholder — mag vernieuwd)

| State | Label (NL) | Accent nu |
|-------|------------|-----------|
| IDLE + bestemming | bestemmingsnaam | muted grijs |
| RECORDING | Opname | `#ff4d4d` |
| TRANSCRIBING | Transcriberen / `Transcriberen {n}%` | `#ffb020` |
| CANCELLED | Geannuleerd | muted |
| ERROR | Mislukt | `#ff5252` |
| Achtergrond capsule | — | `#202124` |
| Tekst | — | `#f1f3f4` |

Gewenst: een helder, toegankelijk systeem (niet alleen kleur; vorm/icoon mee).
Light theme is optioneel; **donkere capsule** past bij “HUD over lichte documenten”.

## Interacties om mee te ontwerpen

1. **Klik ● / ■** — start/stop (toggle) of press/release (PTT).
2. **Sleep body** — verplaatsen.
3. **×** — idle-pill wegklikken.
4. **Rechtsklik** — menu (niet visueel uitwerken, wel ruimte in hit-area laten).
5. **Waveform / marching dots** — subtiele motion, geen afleiding.

## Designprincipes

1. **Leesbaar in perifere blik** — status in <1 s, ook op 125–150% Windows-schaal.
2. **Geen focus stelen** — gedrag is productconstraint; design mag dat niet ondermijnen.
3. **Één job** — status + start/stop + bestemming; geen Meeting Buddy-agenda hier.
4. **Familie met Meeting Buddy** — zelfde merktaal, andere vormfactor.
5. **Desktop-native, kalm** — Windows/macOS; geen speelse consumer-AI look.
6. **i18n** — labels NL/EN/DE; houd tekstzone flexibel (Duits is langer).

## Frames (minimaal)

1. Idle + bestemming “Notulen Q3”
2. Opname + waveform + tag `toggle`
3. Opname + tag `meeting`
4. Transcriberen 67% + marching dots
5. Fout / geannuleerd (één frame elk)
6. Optioneel: idle verborgen vs. zichtbaar

## Merk & tone

- Product: **praatMaar**; de pill heeft geen eigen productnaam in het label.
- Tone: zakelijk, kort, lokaal/privacy hoeft niet op de pill.
- Iconografie: map (bestemming), record/stop, statusdot — geometrisch, scherp op retina.

## Leveringen

- Figma/PDF: alle states hierboven.
- Componenten: capsule, dot, waveform, marching dots, map-icoon, record/stop/dismiss.
- Kleuren + type (systeemvriendelijk: Segoe / SF Pro-equivalent).
- Specificatie hit-areas (min. ~32×32 voor knoppen).
- Korte motion-notes (pulse, bars, dots).

## Wat níet

- Transcript-preview in de pill.
- Chat/AI-bubble styling.
- Volledige Meeting Buddy-UI in de pill.
- Tray-icoon redesign (mag later; optioneel silhouette-afstemming).

## Relatie tot andere briefs

| | Pill | Meeting Buddy overlay |
|--|------|------------------------|
| Moment | Dicteren (kort) | Vergadering (lang) |
| Inhoud | Status + waveform + bestemming | Agenda, hints, samenvatting, vragen |
| Formaat | Smalle capsule ~340×60 | Compact paneel ~320–380 breed |
| Focus | Nooit stelen | Nooit stelen |
