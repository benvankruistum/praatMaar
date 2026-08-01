# Designbrief — Modules (praatMaar)

## Product in één zin

**praatMaar** heeft een hybride modulesysteem: ingebouwde uitbreidingen die je
aan/uit zet. Het **Modules**-scherm is de plek om die extensies te beheren, een
globale optie voor incrementele transcriptie te zetten, en — voor ingeschakelde
modules met acties — direct knoppen te gebruiken (start meeting, Ollama-status, …).

## Wat we zoeken

Vormgeving van het **Modules-dialoogvenster** (tray → Modules): overzicht van
modulekaarten, enable-toggles, actieknoppen, en Opslaan/Annuleren.

Niet in scope als onderdeel van *dit* venster (wel familie / aparte briefs):

- Diepe module-eigenschappen (bijv. Meeting Buddy **Eigenschappen** →
  [meeting-buddy.md](meeting-buddy.md))
- Algemene app-instellingen ([settings.md](settings.md))
- Bestemmingen ([destinations.md](destinations.md))

Tray-cascades (**Meeting Buddy ▸**, **Local LLM ▸**) spiegelen dezelfde acties;
licht meenemen voor consistentie van labels/iconen, geen apart tray-redesign verplicht.

## Rol van het scherm

| Doet | Doet niet |
|------|-----------|
| Modules aan/uit (persist na Opslaan) | Dicteer-microfoon/sneltoets (→ Instellingen) |
| Incrementele transcriptie (globale flag) | Bestemmingen |
| Actieknoppen tonen als module enabled + running | Volledige Meeting Buddy overlay |
| Venster blijft open na Opslaan (zodat acties meteen bruikbaar zijn) | Plugin-store / download van derden |

**Productregel:** modules zijn **ingebouwd** (geen dynamische plugin-install in v1).
Lijst is vaste set uit de app.

## Informatie-architectuur

Titel: **praatMaar — Modules**

### Zones (boven → onder)

| Zone | Inhoud |
|------|--------|
| Intro | Korte uitleg + tip over event-journal (`events/events.jsonl`) — graag compacter dan nu |
| Globale optie | Checkbox **Incrementele transcriptie** + knipmodus (vast/VAD/hybride),
VAD-ms en chunk-seconden (chunk-pipeline; bij stop concatenatie + staart) |
| Lijstheading | “Ingebouwde modules” |
| Modulekaarten | Per module: naam, Ingeschakeld-toggle, beschrijving, optionele actieknoppen |
| Footer | Annuleren · Opslaan |

### Modulekaart (herhaalbaar patroon)

```text
┌─ Module naam ─────────────────────────────┐
│ ☑ Ingeschakeld                            │
│ Korte beschrijving (wrap, muted)          │
│ [ Actie 1 ] [ Actie 2 ] …                 │  ← alleen als enabled én acties bestaan
└───────────────────────────────────────────┘
```

**Actieknoppen** verschijnen pas als de module na Opslaan echt enabled/running is.
Voor Opslaan: gebruiker kan toggles wijzigen; acties horen bij de *actieve*
configuratie.

### Huidige modules (inhoud voor copy/hiërarchie)

| Module | Rol (kort) | Voorbeeldacties |
|--------|------------|-----------------|
| Inbox-spiegel | Kopieert opgeslagen transcripts naar inbox-map | — |
| Speaker Detection | Sprekerlabels `spk_n` (single-mic clustering) of bron ME/OTHER | — |
| Audio-opname | Continue mic (+ optioneel loopback) voor modules | — |
| Spraak-naar-tekst | Live transcriptiedelta’s via gedeeld Whisper | — |
| Meeting Buddy | Vergaderhints, agenda, overlay (experimenteel) | Start… / Start snel / Stop / Agenda / Eigenschappen |
| Local LLM | Ollama + Qwen als lokale AI-provider (standaard uit) | Status / Ollama installeren / Model downloaden |

Lange technische beschrijvingen (audio-capture, STT) nu: graag **scannable** —
één zin primary + optioneel “meer info” of kortere body.

**Afhankelijkheden (visueel hinten mag, geen enforced wizard):** Meeting Buddy
profitteert van audio-capture + STT + optioneel Local LLM; Local LLM heeft
externe Ollama nodig. Design mag subtiele “vereist …”-chips of helpertekst
tonen zonder een dependency-graph UI.

## Interacties

1. Toggle **Ingeschakeld** per module (lokaal tot Opslaan).
2. **Opslaan** → settings toepassen; dialoog **blijft open**; actieknoppen
   verschijnen/verdwijnen.
3. **Annuleren** / sluiten → geen persist van unsaved toggles (huidig: sluit zonder
   save; bevestig gedrag in implementatie — design: duidelijke primary Opslaan).
4. Klik actie → opent module-eigen dialoog of statusmelding (buiten dit scherm).
5. Incrementele transcriptie is **globaal**, niet per module — visueel scheiden
   van de modulelijst.

## Designprincipes

1. **Catalogus, geen dashboard** — één kolom kaarten; geen KPI’s of grafieken.
2. **Enable eerst, acties daarna** — acties zijn secondary tot de module aan staat.
3. **Experimenteel markeren** — Meeting Buddy / Local LLM / loopback-achtige
   features mogen een rustige badge “Experimenteel” krijgen.
4. **Privacy-local** — Local LLM = lokaal; geen cloud-CTA’s.
5. **Familie** — zelfde dialoogtaal als Instellingen/Bestemmingen; microfoonicoon
   op venster (tray-silhouet) blijft.
6. **Scannable copy** — beschrijving max. 2 regels in de kaart; details in Help.
7. **i18n** — actieknoppen naast elkaar; wrapping/stacking op smalle breedte voorzien.
8. **Toegankelijk** — duidelijke heading per kaart; checkbox + naam gekoppeld.

## Frames (minimaal)

1. **Alles uit** — geen actieknoppen; Meeting Buddy/Local LLM disabled.
2. **Meeting Buddy aan** — actierij zichtbaar (5 knoppen — layout/wrapping).
3. **Local LLM aan** — status/install/download-acties.
4. **Na Opslaan** — zelfde venster, acties net verschenen (micro-state).
5. **Incrementele transcriptie aan** — globale checkbox emphasized.
6. Optioneel: lange Duitse labels op actieknoppen (wrapping-stress test).

## Merk & tone

- Titel: **praatMaar — Modules**.
- Tone: helder; “capability”/journal mag in intro kort of naar Help.
- Iconen: per module optioneel (mic, users, brain/local) — geometrisch, geen emoji-clutter.

## Leveringen

- Figma/PDF: dialoog + states hierboven.
- Componenten: intro, global checkbox, module card (off / on / on+actions),
  action button row, experimental badge, footer.
- Suggestie voor actie-overflow als er >4 knoppen zijn (wrap vs. menu) —
  Meeting Buddy heeft er vijf.

## Wat níet

- Plugin marketplace of sideload.
- Module-config JSON-editors in dit scherm.
- Volledige Meeting Buddy overlay of Local LLM setup-wizard *in* de kaart
  (acties openen eigen flows).
- Instellingen-tabs hier herhalen.

## Relatie tot andere briefs

| | Modules | Instellingen | Meeting Buddy | Local LLM-acties |
|--|---------|--------------|---------------|------------------|
| Rol | Extensies aan/uit + entry acties | Kern-dicteerpref | Live vergader-UI | Setup/status |
| Moment | Af en toe | Af en toe | Tijdens meeting | Eerste setup |
| Vorm | Kaarten-dialoog | Tabs-dialoog | Overlay | Status/dialogs vanuit acties |

Zelfde **familielid**; Modules is de “lichtschakelaar + startknoppen” voor
extensies.
