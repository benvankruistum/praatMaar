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

## Agent-prompt (plakken)

```text
Fidelity-pass voor surface <NAAM> canvas-anker <ID>.
Lees docs/design/fidelity-pass.md + open docs/design/canvas/praatMaar-ui.dc.html#<ID>.
Implementeer 1:1 naar canvas: layout, spacing, kleuren, componenten.
Tokens alleen via ui/theme.py. Afwijkingen alleen toolkit-pyside6 hard constraints.
Vink de checklist in fidelity-pass.md af in de commit message.
Niet klaar zonder live vergelijking met de canvas.
```
