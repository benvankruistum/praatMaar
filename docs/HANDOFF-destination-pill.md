# Handoff — Destination-pill: map-icoon + sluitknop

Geschreven 2026-07-19. Bedoeld om in een **nieuwe sessie** te bouwen.
Werktaal: **Nederlands**.

## Repo-status (op moment van schrijven)

| Item | Status |
|------|--------|
| Branch `feat/destination-auto-paste` | Gecommit + gepusht; PR open |
| PR | https://github.com/benvankruistum/praatMaar/pull/9 — *Automatisch plakken per bestemming* |
| Working tree | Clean (niets openstaand te committen voor auto-paste) |
| Dit handoff-onderwerp | **Nog niet geïmplementeerd** (alleen ontwerp-akkoord in chat) |

**Aanbevolen start in de nieuwe sessie:**

1. Check of PR #9 gemerged is; zo ja: `git switch main && git pull`.
2. Nieuwe branch, bijv. `feat/destination-pill-dismiss` vanaf actuele `main`.
3. Bouw onderstaande UI; **niet** opnieuw brainstormen over de beslissingen.

## Goedgekeurde beslissingen

### Map-icoon

- In **idle** met actieve bestemming: klein **map-icoon** vóór de bestemmingsnaam.
- Geen emoji-afhankelijkheid — eenvoudige geometrie (canvas / drawn) of een
  Unicode-maptekst die op Windows én macOS netjes rendert.
- Doel: duidelijk maken dat de pill een **doelmap** toont, niet een status.

### Sluitknop (×)

- Alleen zichtbaar in **idle + actieve bestemming** (naam in beeld).
- **Niet** tijdens Opname / Transcriberen / Geannuleerd / Fout.
- Klik → pill **verbergen**; sticky bestemming blijft actief (transcripts gaan
  nog naar die map).
- Pill weer tonen na:
  - start van een **nieuwe dicteerbeurt**, of
  - **wissel/reset** van bestemming (ook opnieuw dezelfde actief zetten).
- Niet weer tonen bij zomaar idle-terugkeer na cancel/fout zonder die triggers
  (tenzij dat toch nodig blijkt bij implementatie — dan vasthouden aan “na
  dicteerbeurt of bestemming-wissel”).

## Technische aanknopingspunten

| Bestand | Rol |
|---------|-----|
| `indicator/_win.py` | Tk-canvas pill; idle-tak in `_render` / `_apply_idle_visibility`; `set_destination` |
| `indicator/_mac.py` | NSPanel + NSTextField; `_render_labels` / `_apply_idle_visibility` |
| `indicator/_contract.py` | `destination_display_name`, breedte/constanten |
| `dictation.py` | `_handle_destination_command`, `indicator.set_destination` — hier “weer tonen” bij wissel |
| `opnamesessie.py` | `start()` → `notify(RECORDING)` — hier “weer tonen” bij nieuwe beurt |

Huidig idle-gedrag: pill blijft zichtbaar zolang `_destination` gezet is
(`_apply_idle_visibility`). Nodig: flag zoals `_destination_pill_dismissed`
(of equivalent), gezet door ×, gereset bij RECORDING-start / `set_destination`.

**Windows:** × als klikbaar canvas-item (of klein hit-area); let op
`WS_EX_NOACTIVATE` — klik mag focus van het actieve veld niet stelen.
**macOS:** klikbare control op nonactivating panel (zelfde constraint).

## Buiten scope (niet in deze taak)

- Prefix-per-beurt bestemmingsrouting (bewust uitgesteld tot gebruikersfeedback)
- Auto-paste per bestemming (zit in PR #9)

## Acceptatiechecklist

- [ ] Idle + actieve bestemming: map-icoon + naam + × zichtbaar
- [ ] × verbergt pill; volgende dicteer-take landt nog in die map
- [ ] Na nieuwe opname (of bestemming-wissel) pill weer zichtbaar (idle)
- [ ] Geen × tijdens recording/transcribing
- [ ] Windows én macOS (of expliciet noteren als Mac later)
- [ ] Geen focus-diefstal

## Gerelateerde docs

- Spec auto-paste: `docs/superpowers/specs/2026-07-19-destination-auto-paste-design.md`
- Help bestemmingen: `docs/user/help.nl.md`
- Context: `CONTEXT.md` (term *bestemming*, *indicator*)
