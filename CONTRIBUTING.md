# Bijdragen aan praatMaar

Bedankt voor je interesse. Dit is een kleine Windows-desktopapp; houd wijzigingen
gericht en lees eerst [README.md](README.md) en [CONTEXT.md](CONTEXT.md).

## Omgeving

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m ruff format .
```

Op macOS/Linux: zelfde met `.venv/bin/activate`.

Python **3.10+**, Windows en macOS. Zie [docs/STATUS.md](docs/STATUS.md)
voor platformstatus.

## Domeintaal

Gebruik de termen uit `CONTEXT.md` (bijv. `host`, dicteercyclus, indicator).
Wijk niet af naar synoniemen in issues, specs of PR-titels. Bestaande
beslissingen staan in `docs/adr/`.

## Modules

praatMaar heeft een hybride module-systeem ([ADR-0003](docs/adr/0003-hybrid-module-system.md)):

- **Externe integratie** (scripts, andere apps): lees het event-journal —
  [docs/modules-integration.md](docs/modules-integration.md)
- **Ingebouwde module via PR**: volg de authoring-checklist —
  [docs/modules-authoring.md](docs/modules-authoring.md)

v1: geen plugin-installatie buiten de repo; modules worden geregistreerd in
`modules/registry.py`.

## Code-stijl

- Nederlands in gebruikersgerichte strings en module-docstrings (bestaande stijl).
- Geen onnodige refactor buiten de scope van je PR.
- OS-specifieke code hoort achter de `host`-seam (of een toekomstige GUI-seam),
  niet verspreid door `dictation.py`.
- Voeg tests toe voor pure logica (`hotkeys`, `config`, `recovery`, …).
- Linting/formatting met **Ruff** (config in `pyproject.toml`). CI draait
  `ruff check` en `ruff format --check`. Voor commit: `ruff check --fix .`
  en `ruff format .`.

## Tests en CI

- Lokaal: `requirements-dev.txt` (runtime + pytest + ruff).
- CI test installeert `requirements.txt` + pytest — dezelfde runtime-deps als de app.
- Veel tests importeren via `modules.registry`; dat laadt **alle** ingebouwde
  modules eager. Nieuwe runtime-deps horen in `requirements.txt` / `pyproject.toml`,
  anders faalt CI met importfouten (niet alleen de nieuwe tests).

Zie ook [docs/modules-authoring.md](docs/modules-authoring.md) (valkuilen).

## Git-workflow

We werken **altijd via feature-branches**. Direct op `main` committen of
pushen is niet toegestaan (niet voor mensen, niet voor agents).

1. Update `main` (`git checkout main && git pull`).
2. Maak een branch vanaf `main` (bijv. `feat/…`, `fix/…`, `cursor/…`).
3. Commit alleen op die branch; open een PR naar `main`.
4. Rebase op `main` vóór merge als `main` is vooruitgelopen.
5. Force-push alleen op **jouw** feature-branch (`--force-with-lease`), nooit op `main`.

Zit je per ongeluk op `main` met lokale wijzigingen: meteen
`git switch -c <branch>` vóór je commit.

## Pull requests

1. Branch vanaf `main` (zie hierboven) — geen commits op `main`.
2. Kleine, reviewbare PR’s met een korte uitleg van **waarom**.
3. Zorg dat `pytest` en `ruff` (check + format) groen zijn.
4. Vermeld Windows-/macOS-teststappen als je UI, hotkeys of packaging raakt.

## Issues

Gebruik de issue-templates onder `.github/ISSUE_TEMPLATE/`. Security: zie
[SECURITY.md](SECURITY.md) — geen publieke exploit-details.

Lokale agent-notities onder `.scratch/` zijn optioneel en **niet** de publieke
tracker; die is GitHub Issues.
