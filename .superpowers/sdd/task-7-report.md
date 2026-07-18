# Task 7 Report — Help tray-item + dialog + user docs

**Status:** ✅ Complete  
**Date:** 2026-07-18

## Delivered

- **`docs/user/help.nl.md`, `help.en.md`, `help.de.md`** — volledige gebruikerstekst: bestemmingen/sticky/pill, stem-wissel (exact + standaard), bestandslocaties, tray-beheer, risico's
- **`help_dialog.py`** — `open_help(parent)`; ScrolledText readonly; `user_docs_dir()` voor repo + `_MEIPASS`; fallback via `help.fallback`
- **`tray.py`** — menu: Instellingen | Bestemmingen | Help | — | Afsluiten; `on_help` callback
- **`dictation.py`** — `open_help()` via `call_on_main`
- **`locales/*.json`** — `tray.help`, `help.title`, `help.close`, `help.fallback`
- **`praatMaar.spec` / `pyproject.toml`** — bundle `docs/user`; module `help_dialog`
- **`tests/test_help_dialog.py`** — pad + laden + fallback

## Tests

```
pytest -q → 39 passed
```

## Commit

```
Voeg Help-menu en gebruikersdocumentatie toe.
```

## Review fix (tray vs. dialoog)

- **Help NL/EN/DE** — tray-sectie herschreven: menu = Instellingen, Bestemmingen, Help, Afsluiten; map-knoppen staan in de Bestemmingen-dialoog, niet in het tray-menu
- **Help NL** — resetwoord altijd *standaard* toegevoegd (was al in EN/DE)
- **`tray.py`** — module-docstring vermeldt Bestemmingen + Help
