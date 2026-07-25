# Fidelity-pass — canvas exact (agent-opdracht)

> **Status:** actief op `feat/pyside6-ui`  
> **Doel:** Qt-UI gelijk trekken met [canvas/praatMaar-ui.dc.html](canvas/praatMaar-ui.dc.html)  
> **Bar (aangescherpt):** canvas layout, spacing, kleuren, componenten **exact**; alleen OS-titlebar en system fonts mogen native afwijken ([toolkit-pyside6.md](toolkit-pyside6.md) hard constraints).

## Acceptatieregels (niet onderhandelbaar)

1. **Bron:** bij conflict wint de **canvas-frame** (ankers hieronder). Markdown-briefs zijn toelichting.
2. **Tokens:** alle kleuren/radii/type uit `ui/theme.py` — geen losse hex in dialogen behalve via `TOKENS[...]`.
3. **Afwijkingen:** alleen wat toolkit verbiedt (custom titlebar, zware blur/shadow als Qt dat niet betrouwbaar kan → lichte border i.p.v. canvas-shadow). Elke andere afwijking = **niet klaar**.
4. **Done:** surface is klaar als (a) checklist 100% af, (b) live app naast canvas bekeken, (c) gebruiker ok zegt. Tests groen ≠ done.

## Frames

| Surface | Canvas | Qt-entry |
|---------|--------|----------|
| Modules | `#5a` | `ui/dialogs/modules.py` |
| Instellingen | `#4a` | `ui/dialogs/settings.py` |
| Bestemmingen | `#3a` | `ui/dialogs/destinations.py` |
| Pill | `#2a` | `indicator/_qt.py` |
| Meeting Buddy overlay | `#1a` | `modules/_builtin/meeting_buddy/overlay.py` |

## Volgorde

1. Modules `#5a` (hoogste zichtbaarheid)
2. Bestemmingen `#3a`
3. Instellingen `#4a`
4. Pill `#2a`
5. Meeting Buddy `#1a`

Eén surface per sessie/PR-slice tenzij expliciet anders.

## Checklist — Modules `#5a`

Kopieer naar de PR/commit-body en vink af:

- [x] Dialoogbreedte ~620px-familie; content `#fff`
- [x] Intro: 12.5px, kleur `#3B4652`, compact
- [x] Globale optie “Incrementele transcriptie” in eigen bordered box (aan = accent soft)
- [x] Sectielabel “INGEBOUWDE MODULES”: uppercase, muted
- [x] Modulekaart **uit**: bg `#FCFDFD`, border `#E4E7EC`, radius 6
- [x] Modulekaart **aan**: bg `#fff`, border `#CFE2F4`
- [x] Toggle rechts; naam links bold 13px
- [x] Badge `experimenteel` op Meeting Buddy + Local LLM
- [x] “draait”-stip groen als module enabled/running
- [x] Actierij; eerste actie primary, rest secondary
- [x] Footer: Annuleren ghost + Opslaan primary
- [x] Na Opslaan: statusregel + dialoog blijft open; acties verschijnen
- [ ] Live screenshot / side-by-side met canvas M1/M2 goedgekeurd door gebruiker

## Checklist — Instellingen `#4a`

- [x] Sectiekopjes MICROFOON / INDICATOR / BEDIENING / OPTIES
- [x] Labelkolom ~150px; control rechts
- [x] Warm-houden onder microfoon met aparte hintregel
- [x] Modus als radio’s (niet dropdown)
- [x] Sneltoets als keycaps + knop Opnemen…
- [x] Opties: normale checkboxes + hint onder automatisch plakken
- [x] Footer: Annuleren ghost + Opslaan primary
- [ ] Live side-by-side met canvas S1 goedgekeurd door gebruiker

## Checklist — Bestemmingen `#3a`

Hoofddialoog:

- [x] Family-shell: `body` + `dialogFooter`-frame (idioom `modules.py`); breedte ~760px
- [x] Intro: licht paneel + rond `?`-badge + 3 regels (stemwoorden vet, 1 muted hint)
- [x] Tabel: kolommen Naam/Map/Plakken/Opslag/Actief, rijhoogte 44px, 3px accent-strip
- [x] Standaard-rij: systeemband, map-icoon, badge **systeem**, "App-opslagmap" muted
- [x] Custom-rij: map-icoon, naam 13.5/600, pad monospace muted
- [x] Gedeelde/onveilige map: amber ⚠ naast pad (heuristiek `is_shared_location`)
- [x] Actieve rij: accent-strip + lichte tint + pill **✓ Actief**
- [x] Selectie: accent-rand om rij (los van "actief")
- [x] Actierij: Toevoegen (primary) · Wijzigen · Actief zetten · Verwijderen (danger); rechts map-open links
- [x] Standaard geselecteerd: Wijzigen/Verwijderen disabled + inline hint (geen messagebox)
- [x] Empty state: dashed map-icoon + kop + tekst + primary CTA
- [x] Footer: band + muted note + Annuleren ghost + Opslaan primary

Subdialoog:

- [x] Verticale veldstack: label (600 + rode `*`) + control + hint
- [x] Naam met hint; focus-ring
- [x] Opslag als twee radio's (geen dropdown)
- [x] Append-bestandveld ingesprongen, alleen bij "toevoegen"; met hint
- [x] Inline validatie (rode rand + ⚠-regel), amber "gereserveerde namen"-infobox; geen messagebox
- [x] Live side-by-side met canvas B1–B6 goedgekeurd door gebruiker

## Checklist — Pill `#2a`

- [x] Capsule 340×60, radius 30, bg `#1C1F23`, state-getinte 1px rand
- [x] Kleuren canvas: opname `#FF5C57`, transcriberen `#FFB020`, geannuleerd `#8B929B`, fout `#FF6B6B`
- [x] Idle: map-icoon + naam + subregel "Gereed · <sneltoets>" + 32px record/✕ hit-areas
- [x] Opname: pulse-dot + 18-bar waveform + modus-tag pill (↔/●) + vierkante stop in ronde ring
- [x] Meeting-modus: tag met blauw accent (`#7FB1E0`/`#BFD8EF`)
- [x] Transcriberen: draaiende arc + "{n} %" tabular + marching dots + voortgangsdraad onderaan; geen stop
- [x] Geannuleerd: doorgestreepte ring + "niets ingevoegd"
- [x] Fout: driehoek + rood-getinte capsule + sneltoets-hint
- [x] Vorm draagt betekenis (dot · arc · doorgestreept · driehoek · map) — leesbaar in grijswaarden
- [x] Live side-by-side met canvas P1–P6 goedgekeurd door gebruiker

## Agent-prompt (plakken)

```text
Fidelity-pass voor surface <NAAM> canvas-anker <ID>.
Lees docs/design/fidelity-pass.md + open docs/design/canvas/praatMaar-ui.dc.html#<ID>.
Implementeer 1:1 naar canvas: layout, spacing, kleuren, componenten.
Tokens alleen via ui/theme.py. Afwijkingen alleen toolkit-pyside6 hard constraints.
Vink de checklist in fidelity-pass.md af in de commit message.
Niet klaar zonder live vergelijking met de canvas.
```
