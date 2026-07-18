# Bijdragen aan praatMaar

Bedankt voor je interesse. Dit is een kleine Windows-desktopapp; houd wijzigingen
gericht en lees eerst [README.md](README.md) en [CONTEXT.md](CONTEXT.md).

## Omgeving

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
```

Python **3.10+**, Windows. macOS-wijzigingen zijn welkom, maar de app is
daar nog niet ondersteund — zie [docs/STATUS.md](docs/STATUS.md).

## Domeintaal

Gebruik de termen uit `CONTEXT.md` (bijv. `host`, dicteercyclus, indicator).
Wijk niet af naar synoniemen in issues, specs of PR-titels. Bestaande
beslissingen staan in `docs/adr/`.

## Code-stijl

- Nederlands in gebruikersgerichte strings en module-docstrings (bestaande stijl).
- Geen onnodige refactor buiten de scope van je PR.
- OS-specifieke code hoort achter de `host`-seam (of een toekomstige GUI-seam),
  niet verspreid door `dictation.py`.
- Voeg tests toe voor pure logica (`hotkeys`, `config`, `recovery`, …).

## Pull requests

1. Fork / branch vanaf `main`.
2. Kleine, reviewbare PR’s met een korte uitleg van **waarom**.
3. Zorg dat `pytest` groen is.
4. Vermeld Windows-teststappen als je UI, hotkeys of packaging raakt.

## Issues

Gebruik de issue-templates onder `.github/ISSUE_TEMPLATE/`. Security: zie
[SECURITY.md](SECURITY.md) — geen publieke exploit-details.

Lokale agent-notities onder `.scratch/` zijn optioneel en **niet** de publieke
tracker; die is GitHub Issues.
