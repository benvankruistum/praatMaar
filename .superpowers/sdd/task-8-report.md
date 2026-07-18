# Task 8 Report — CONTEXT/CHANGELOG/README + integratiecheck

**Status:** ✅ Complete  
**Date:** 2026-07-18

## Delivered

- **`CONTEXT.md`** — glossariumterm **bestemming** (naam+map, sticky, stem exact match, pill, tray Bestemmingen)
- **`CHANGELOG.md`** — Unreleased: bestemmingen, Help-tray, map openen
- **`README.md`** — korte vermelding Bestemmingen + Help in tray-tabel
- **`dictation.py`** — `apply_settings`: revalideer `ACTIVE_DESTINATION` als alleen `destinations` wijzigt

## Tests

```
pytest -q → 39 passed
```

## Commit

```
Documenteer bestemmingen en Help in CONTEXT/CHANGELOG.
```

## Final fix — naamvalidatie (review)

- **`destinations.py`:** `is_reserved_name`, `find_normalized_collision`; `sanitize_destinations` filtert gereserveerde en genormaliseerde duplicaten
- **`destinations_dialog.py`:** validatie bij toevoegen/wijzigen met i18n-foutmeldingen
- **Tests:** 3 nieuwe tests; `pytest -q` → 42 passed

**Commit:** `Valideer bestemmingsnamen op spraakbotsingen en gereserveerde naam.`
