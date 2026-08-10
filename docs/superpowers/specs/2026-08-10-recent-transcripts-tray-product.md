# Product specification — Recente transcripts vanuit tray

## Status
Accepted

## Context
praatMaar schrijft elk geslaagd transcript al naar schijf via `recovery.save_transcript`
(default `%APPDATA%\praatMaar\transcripts\`, of map van de actieve bestemming).
Default-map pruneert tot nieuwste 50 (`MAX_TRANSCRIPTS`). Bestandsnamen:
`YYYY-MM-DD_HHMMSS.txt` (plus `_N` bij botsing).

Het gedeelde contextmenu zit in `ui/tray.py` → `build_context_menu_entries`
(tray én indicator/pill). **Herstel-audio** in Instellingen betreft mislukte
transcripties (WAV’s) — dit is een ander probleem: hergebruik van **geslaagde** tekst.

## Problem
Na een geslaagde dicteercyclus kan de gebruiker de transcripttekst kwijt zijn in
het doelveld terwijl die wel lokaal is opgeslagen. Er ontbreekt een snelle,
niet-focus-stelende route vanuit tray/indicator om recente succesvolle
transcripts te selecteren en opnieuw te gebruiken.

## Goal
Vanuit het gedeelde tray/indicator-contextmenu de nieuwste geslaagde
dicteer-transcripts (max. 5) tonen als datum/tijd-labels; bij keuze de
bijbehorende tekst op het klembord zetten zodat de gebruiker zelf kan plakken.

## Non-goals
- Geen beheer/verwijderen/hernoemen van transcripts in deze slice.
- Geen preview van de volledige tekst in het menu.
- Geen automatisch plakken (`host.paste`) na selectie.
- Geen “bestand openen” / Verkenner vanuit dit menu (v1).
- Geen nieuwe Instellingen-optie voor aantal of bronmap.
- Geen wijziging aan herstel-audio of recovery-WAV-flow.
- Geen Meeting Buddy-transcriptjournals / meeting-transcripten.
- Geen inbox-spiegel-kopieën als aparte bron.
- Geen append-modus bestemmingen als sessie-items.
- Geen cloud, sync of externe sharing.
- Geen doorzoeken / filteren / history-browser UI.

## Users and scenarios
**Primaire gebruiker:** Windows-gebruiker die meerdere dicteercycli achter elkaar doet.

1. Mislukte plak → tray → Recente transcripts → nieuwste → klembord → handmatig plakken.
2. Tekst gewist → zelfde pad voor een eerdere dicteercyclus.
3. Actieve bestemming (directory-save) → discrete `.txt` in top-5.
4. Lege history → empty state, geen crash.
5. Indicator-menu → zelfde cascade als tray.

## Functional requirements
- **FR-01** Cascade **Recente transcripts** in gedeeld tray/indicator-menu (na Bestemmingen).
- **FR-02** Maximaal **5** recente discrete transcriptbestanden, nieuwste eerst.
- **FR-03** Submenu-regel = datum + tijdstip (geen volledige tekst).
- **FR-04** Bron: default transcripts-map + opslagmappen van directory-bestemmingen
  (`file_mode=new`); timestamp-patroon `YYYY-MM-DD_HHMMSS` optioneel `_N`.
- **FR-05** Ranking op mtime, nieuwste eerst; tie-break op naam.
- **FR-06** Klik → UTF-8-tekst op klembord; geen paste; geen focus-stelend venster.
- **FR-07** Empty state: disabled regel met i18n-tekst.
- **FR-08** Leesfout bij klik: klembord ongewijzigd; geen crash.
- **FR-09** Append-modus levert geen cascade-items.
- **FR-10** Meeting Buddy-paden niet in de lijst.
- **FR-11** Geen nieuwe config-keys of Instellingen-UI.

## Quality requirements
- **QR-01** Geen focus steal.
- **QR-02** Local-first; geen transcripttekst in event-journal.
- **QR-03** Lichte scan (geen zware recursie).
- **QR-04** i18n `nl`/`en`/`de`.
- **QR-05** Zelfde gedrag tray én indicator.
- **QR-06** Labels niet verwarren met herstel-audio.
- **QR-07** Ontoegankelijke map overslaan zonder cascade te breken.

## Supported platforms
| Platform | Verwachting v1 |
|----------|----------------|
| Windows 10/11 | Must |
| macOS | Should |
| Linux (experimenteel) | Could |

## Edge cases
Zie assessment in chat: empty, append-only, sticky bestemming, prune, collision
`_N`, missing file na openen, ontoegankelijke map.

## Privacy considerations
Leest lokale transcriptbestanden; schrijft naar OS-klembord (zelfde profiel als
normale dicteer-copy). Geen logging van inhoud; geen cloud; geen retentiewijziging.

## Dependencies
`recovery.save_transcript` / `transcripts_dir`; `destinations.py`; `ui/tray.py`;
clipboard helpers in `dictation.py`; `locales/`.

## Risks
Append-modus niet zichtbaar → documenteren; duplicate datetime-labels → `_N` in label.

## Acceptance criteria
1. Discrete timestamp-`.txt` in default-map → zichtbaar in cascade (max 5, nieuwste eerst).
2. Klik → klembord gevuld; geen paste; geen focus-venster.
3. Geen matching files → empty state, geen crash.
4. Sticky directory-bestemming met nieuwer bestand → in top-5.
5. Append-only → niet als sessie-items.
6. Indicator-menu = zelfde cascade.
7. Strings vertaald in `nl`/`en`/`de`.
8. Ontoegankelijke bestemming-map → overige items blijven; geen crash.

## Required evidence
Unit tests (listing, empty, skip dirs, pattern, copy); Windows smoke tray+pill;
privacy note; i18n; help-vermelding.

## Agent ownership
- **Responsible:** `core-python-architect`
- **Consult:** `ux-product-design`, `privacy-security`
- **Reviewers:** UX (licht), privacy-security, `/code-review`; `quality-release` bij acceptatie
- **Acceptatie:** `product-owner`

## Open questions
Geen — actie = alleen klembord; bron = default + directory-bestemmingen; count = 5.
