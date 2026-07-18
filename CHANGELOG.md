# Changelog

Alle noemenswaardige wijzigingen aan dit project worden hier bijgehouden.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en dit project volgt [SemVer](https://semver.org/lang/nl/).

## [Unreleased]

### Added

- Publieke-repo basics: LICENSE (MIT), README, SECURITY, CONTRIBUTING, CHANGELOG
- `pyproject.toml`, `requirements.txt` / `requirements-dev.txt` met gepinde deps
- `start-praatMaar.bat` / `.vbs` met relatieve paden (vervangt machine-specifieke `start-whisper.*`)
- Bestandslogging naar `%APPDATA%\praatMaar\praatMaar.log` (`app_logging.py`)
- Basis-pytest suite en GitHub Actions (Windows)
- `docs/STATUS.md`; verouderde handoffs gearchiveerd
- `Opnamesessie` (`opnamesessie.py`) — dicteercyclus los van `dictation.py`
- Windows indie-release: Inno Setup-script, `scripts/build-windows.ps1`, Release-workflow

### Changed

- Model-download: fallback repo-id map naast private `faster_whisper.utils._MODELS`
- `dictation.py` is dunne entrypoint (splash, hotkeys, tray); lifecycle in `Opnamesessie`
