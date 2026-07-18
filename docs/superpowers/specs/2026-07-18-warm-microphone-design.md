# Design — optionele warme microfoon

- **Datum:** 2026-07-18
- **Status:** Goedgekeurd (chat)

## Doel

Gebruiker kan kiezen of de microfoonstream warm blijft (snellere start) of
pas bij dicteren opent (minder permanente mic-claim; beter bij autostart).

## Config

```json
"warm_microphone": false
```

Default: `false`. Ontbrekende key = uit.

## Gedrag

| `warm_microphone` | Start | Tussen opnames |
|-------------------|-------|----------------|
| `true` | `warmup_microphone()` na model-load | Stream blijft open |
| `false` | Geen warmup | Stream open bij `start`, dicht na stop/cancel |

Live in Instellingen: uit → stream sluiten; aan → warmup.

## UI

Checkbox in Instellingen, i18n-keys `settings.warm_microphone` (+ korte hint
in het label).

## Buiten scope

Apart autostart-beleid, idle-timeout, per-device policy.
