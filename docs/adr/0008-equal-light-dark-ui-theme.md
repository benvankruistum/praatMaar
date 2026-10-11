# 0008 — Gelijkwaardig licht- en donkerthema

- **Status:** Aanvaard (product-owner in grilling 2026-09-16)
- **Datum:** 2026-09-16
- **Context-term:** geen nieuwe glossary-term — presentatie, niet domein
- **Gerelateerd:**
  [0005 — PySide6 UI toolkit](0005-ui-toolkit-pyside6.md)

## Context

De shipping UI is PySide6 met één light-only token-set (`ui.theme.TOKENS`).
`apply_theme` pin’t Qt op `ColorScheme.Light` zodat Windows dark mode geen
donker palet onder lichte QSS-tekst zet. De **indicator** (pill) is altijd een
donkere HUD; Meeting Buddy-overlay en dialogen zijn licht (canvas `#1a` / `#4a`).

Dat was een bewuste uitstel: designbriefs noemden “light voldoende voor MVP”;
het implementatieplan zette dark mode voor dialogen buiten scope. Meeting Buddy-
mockups (2026-09) vragen een donkere overlay-HUD in dezelfde familie als de
pill, mét een lichte tegenhanger. Productkeuze: licht en donker zijn
**gelijkwaardig** voor de hele praatMaar-UI, niet alleen Meeting Buddy.

## Beslissing

1. **Twee gelijkwaardige thema’s** — dezelfde informatie-architectuur en
   states; twee token-sets (licht en donker). Geen aparte layouts per thema.
2. **Hele UI** — Instellingen, Modules, Bestemmingen, **indicator**, Meeting
   Buddy overlay en dialogen, splash. De pill krijgt ook een lichte variant.
3. **Bron van waarheid voor tokens** blijft `ui.theme` (QSS), niet per-widget
   hex. Dark is een tweede palet achter dezelfde namen, geen parallelle
   stylesheet-boom.
4. **Keuze:** default volgt het OS (Windows/macOS/Linux kleurenschema).
   Optionele override in **Instellingen → Algemeen**: Systeem / Licht / Donker.
   Default van die override is **Systeem**.
5. De Light-pin in `apply_theme` verdwijnt zodra beide paletten bestaan; tot
   die tijd blijft de pin staan (voorkomt onleesbare dialogen).

### Bewust buiten scope

- Per-oppervlak thema (overlay donker, Instellingen licht) als productregel
- User-defined kleuren / high-contrast als derde thema (OS contrast mag
  later; niet in deze beslissing)
- Tray-icoon redesign

## Alternatieven overwogen

- **Alleen OS volgen, geen setting.** Verworpen: gebruiker wil optioneel
  override in Algemeen (Systeem/Licht/Donker).
- **Alleen Meeting Buddy.** Verworpen: “beide letterlijk” — pill en rest van
  de app zouden anders een ander thema houden.
- **HUD altijd donker, dialogen altijd licht.** Verworpen: dat is twee
  families, geen gelijkwaardige thema’s.
- **Light-only houden (huidige pin).** Verworpen: was uitstel, nu ingehaald.

## Gevolgen

- `core-python-architect` implementeert token-paletten, QSS-switch en de
  Instellingen-keuze; platform-agents alleen als no-activate/HUD-flags per
  thema breken.
- Tests moeten beide paletten pinnen; niet alleen `light_palette`.
- Canvas `#1a` (lichte overlay) en de donkere Meeting Buddy-mockups zijn
  beide bronnen: zelfde zones, andere tokens.
- i18n: labels voor Systeem / Licht / Donker in nl/en/de.
- Linux blijft experimenteel; Qt-kleurenschema daar best-effort.

## Verificatie

- Instellingen → Algemeen: Systeem volgt OS; Licht/Donker overschrijven.
- Overlay, pill, één Instellingen-tab en Modules in beide thema’s leesbaar
  (contrast, geen light-QSS op dark Base).
- Theme-wissel zonder herstart, of documenteer herstart als harde limiet.
