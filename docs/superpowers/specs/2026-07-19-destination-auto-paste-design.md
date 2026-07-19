# Design — Automatisch plakken per bestemming

- **Datum:** 2026-07-19
- **Status:** Goedgekeurd (chat)

## Doel

Per sticky bestemming instellen of een geslaagde dicteerbeurt automatisch
naar klembord + plakken mag. Sommige mappen (bijv. boodschappenlijst) zijn
alleen archief; daar mag het klembord niet worden overschreven.

## Beslissingen

| Keuze | Besluit |
|-------|---------|
| Geen actieve bestemming | Globale Instellingen-optie `auto_paste` (ongewijzigd) |
| Actieve bestemming | Flag op die bestemming wint |
| Default nieuwe bestemming | `auto_paste: false` |
| Als `auto_paste` uit | Geen klembord én geen Ctrl/Cmd+V — alleen opslaan in de map |
| Bestaande config zonder key | Behandel als `false` |

## Config

```json
{
  "name": "Boodschappen",
  "path": "C:/werk/notes/boodschappen",
  "auto_paste": false
}
```

`sanitize_destinations` behoudt `auto_paste` als bool; ontbrekend → `false`.

## UI

- Bestemmingen-dialoog: bij toevoegen/wijzigen een checkbox
  “Automatisch plakken” (default uit).
- Lijst: korte kolom of ja/nee-indicator zodat je de keuze ziet zonder te openen.
- Globale checkbox in Instellingen blijft; label/help maakt duidelijk dat die
  alleen geldt zonder actieve bestemming.

## Runtime

Na transcriptie (niet bij bestemming-/reset-commando):

1. Bepaal `effective_paste = resolve_auto_paste(active, destinations, global)`.
2. Sla transcript altijd op via bestaande routing.
3. Als `effective_paste`: klembord + auto-plakken (huidig pad).
4. Anders: sla klembord en paste over.

## Buiten scope

- Per-beurt prefix-routing van bestemmingen
- Apart “alleen klembord”-niveau
- Pill-indicator voor paste-modus

## Risico’s

- Gebruikers die sticky aan hebben staan met `auto_paste: false` merken geen
  plakken — Help moet dit kort noemen.
- Typehint `dict[str, str]` voor destinations moet `Any`/TypedDict worden i.v.m. bool.
