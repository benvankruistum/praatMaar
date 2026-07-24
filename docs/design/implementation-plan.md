# Implementatieplan — praatMaar UI-canvas

- **Datum:** 2026-07-24
- **Bron:** [canvas/praatMaar-ui.dc.html](canvas/praatMaar-ui.dc.html) + briefs in
  deze map
- **Doel:** de goedgekeurde vormgeving gefaseerd nabouwen in de bestaande
  Tk/ttk-UI (geen rewrite naar webview)

## Uitgangspunten

1. **Eén design-systeem eerst** — kleuren, type, knoppen, badges, sectielabels
   als herbruikbare constanten/helpers, niet per dialoog hardcoderen.
2. **Gedrag behouden** — non-activating pill, Modules blijft open na Opslaan,
   i18n nl/en/de, platform-seams (macOS settings-subprocess) ongemoeid.
3. **Tk-realisme** — canvas is HTML; we benaderen waar nodig (ttk-thema,
   Canvas-tekening voor pill/waveform, geen CSS-box-shadow 1:1).
4. **Geen scope creep** — geen transcript in overlay; geen Bestemmingen in
   Instellingen; geen plugin-store.

## Fase 0 — Design tokens & gedeelde dialoog-shell

**Levering:** gedeelde constants + kleine UI-helpers.

| Token / patroon | Canvas-richtlijn |
|-----------------|------------------|
| Accent | `#0F6CBD` (hover `#0A5CA3`) |
| Tekst | `#1B1F24` / muted `#5A6572` / `#8A94A0` |
| Surfaces | dialoog `#fff`, page/bg `#E9EDF2` / `#F7F9FB` |
| Border | `#E1E5EA` / `#EDEFF3` |
| Danger / warn / ok | rood/amber/groen zoals canvas (pill + banners) |
| Type | Segoe UI; labels ~13/600, body ~12–12.5/400 |
| Radius | ~5–8 px knoppen/kaarten |
| Sectielabel | uppercase, letter-spacing, muted |
| Footer | Annuleren (ghost) + Opslaan (primary) |
| Badge | `experimenteel` op modulekaarten |

**Code-richting (voorstel):**

- `ui_theme.py` of `ui/tokens.py` — kleuren + fonts
- `ui_dialog.py` — titelrij, footer, sectielabel (optioneel, incrementeel)
- Bestaande `ui_icon.py` blijft voor venstericoon

**Klaar als:** tokens bestaan; één dialoog (Modules of Bestemmingen) gebruikt ze
als proof.

## Fase 1 — Modules-dialoog (`#5a`)

Hoogste zichtbaarheid / laagste risico voor dicteercyclus.

- Modulekaarten: uit = plat/grijs; aan = wit + blauwe rand + “draait”-stip
- Globale incrementele transcriptie los van de lijst
- Actierij wrap (Meeting Buddy: primaire Starten, rest secondary)
- Experimenteel-badge Meeting Buddy / Local LLM
- Footer: na Opslaan bevestiging “Opgeslagen — acties zijn nu bruikbaar”;
  Sluiten vs Annuleren volgens canvas
- Dependency-hints (muted regels), geen harde blokkade

**Bestanden:** `modules_dialog.py`, locales indien copy wijzigt,
`tests/test_modules_dialog.py`

## Fase 2 — Bestemmingen (`#3a`)

- Tabelrijen 44 px; naam zwaarder dan pad
- Standaard-rij: slot / system band; niet bewerkbaar
- Actief: blauwe strook + label “Actief” (los van selectie-rand)
- Empty state met CTA
- Subdialoog: naam groot + hint; opslag radio’s; append-veld conditioneel
- Inline validatiefouten i.p.v. alleen messagebox (waar praktisch)

**Bestanden:** `destinations_dialog.py`, locales, tests

## Fase 3 — Instellingen (`#4a`)

- Tabs Algemeen / Taal / Geavanceerd in zelfde shell
- Labelkolom ~150 px + control rechts; sectieritme
- Sneltoets: keycaps + blauwe luisterstaat (niet rood)
- Taal: twee blokken met voorbeeldregel
- Geavanceerd: model-radio’s + herstart-notitie; herstel-audio tool-sectie

**Bestanden:** `settings.py` (+ macOS `settings_process` alleen als layout-breuk),
locales, tests

## Fase 4 — Status-pill (`#2a`)

Meeste custom drawing (Canvas / NSView).

- Donkere capsule `#1C1F23`-achtig; states P1–P6 uit canvas
- Idle + bestemming: map + naam + record + ×
- Opname: pulse-dot + 18-bar waveform + modus-tag + stop
- Meeting-tag: blauw accent (link naar Meeting Buddy)
- Transcriberen: arc + % + marching dots + progressdraad
- Geannuleerd / fout: vorm + kleur (grijswaarden-onderscheidbaar)
- Hit-areas ≥ ~32 px

**Bestanden:** `indicator/_contract.py` (kleuren), `_win.py`, `_mac.py`, tests

## Fase 5 — Meeting Buddy overlay + dialogen (`#1a`)

- Overlay-zones: header, banner, agenda-ladder, summary, vragen, hints, footer
- Statusladder: vorm draagt betekenis (○ ◐ ● ✓ of icon-equivalent)
- Hints max 3, één emphasized (blauwe strook)
- Banners: fout rood + actie; “loopt achter” amber zonder knop
- Minimaliseren → donkere mini-pill (familie van `#2a`, kleiner)
- Agenda-dialoog + Eigenschappen in zelfde dialoog-shell als Modules/Instellingen

**Bestanden:** `modules/_builtin/meeting_buddy/overlay.py`,
`agenda_dialog.py`, `properties_dialog.py`, locales, tests

## Fase 6 — Polish & docs

- Help nl/en/de alleen waar UI-copy/gedrag zichtbaar wijzigt
- Screenshots of link naar canvas in STATUS (kort)
- Visuele regressie: handmatige checklist per surface (Win primair)

## Volgorde & parallelisatie

```text
Fase 0 ──► Fase 1 (Modules)
       ├─► Fase 2 (Bestemmingen)     } na tokens; 1–3 parallel mogelijk
       └─► Fase 3 (Instellingen)
Fase 4 (Pill) na tokens; kan parallel met 1–3 als tekenwerk gescheiden blijft
Fase 5 (Meeting Buddy) na Fase 0 + bij voorkeur na Fase 4 (gedeelde statusdot/tags)
Fase 6 sluit af
```

**Aanbevolen eerste PR’s:**

1. Tokens + Modules (Fase 0–1)
2. Bestemmingen (Fase 2)
3. Instellingen (Fase 3)
4. Pill (Fase 4)
5. Meeting Buddy overlay/dialogen (Fase 5)

## Acceptatie per fase

- [ ] Pixel-perfect niet verplicht; wél herkenbaar t.o.v. canvas (kleur, hiërarchie, states)
- [ ] `pytest` groen; `ruff check` / `ruff format`
- [ ] i18n: nieuwe strings in nl + en + de
- [ ] Geen regressie non-activate / macOS settings-subprocess

## Buiten scope (bewust)

- Webview/Electron UI
- Dark mode voor dialogen (pill blijft donkere HUD)
- Tray-icoon redesign
- Plugin marketplace
