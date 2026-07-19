# Changelog

Alle noemenswaardige wijzigingen aan dit project worden hier bijgehouden.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en dit project volgt [SemVer](https://semver.org/lang/nl/).

## [Unreleased]

Nog geen vaste release-datum. Geplande volgende tag: **v0.2.0** (zie
[docs/release-windows.md](docs/release-windows.md) / [docs/release-macos.md](docs/release-macos.md)).

### Added

- Meertaligheid: `speech_language` + `ui_language` (`nl`/`en`/`de`), JSON-locales en `i18n.py`
- Optionele warme microfoon (`warm_microphone`, default uit)
- **Bestemmingen:** sticky transcriptdoelen (naam→map), stemwissel via exacte
  match, actieve naam in de pill, beheer via tray-dialoog
- **Help:** tray-item met lokale gebruikersdocumentatie (`docs/user/help.*.md`,
  nl/en/de)
- Transcriptmap en actieve bestemmingsmap openen vanuit de Bestemmingen-dialoog
- **Herstel-audio:** sectie in Instellingen — lijst/wissen/map openen + opnieuw
  transcriberen (met vraag om WAV te verwijderen na succes)
- **Modules:** tray-dialoog (aan/uit), event-journal (`events/events.jsonl`),
  inbox-spiegel, incrementele transcriptie (`incremental_transcription`)
- Per bestemming optioneel automatisch plakken (`auto_paste`, default uit)
- macOS-port: native NSPanel-indicator (`indicator._mac`, ADR-0002), tray op
  main thread, `host._mac`, TCC- en release-docs, PyObjC-dependency op Darwin
- Ruff lint/format als CI-guardrail
- Cursor project-skills: `/update-documentation` en `/prepare-release`
  (`.cursor/skills/`; zie `CLAUDE.md`)

### Fixed

- Warme microfoonstream heropent na Bluetooth disconnect/reconnect (geen stille lege opnames meer)
- Hotkey-/settings-/splash-labels platform-aware (Mac: Control/Option/Command)
- Diverse macOS-stabiliteitsfixes (settings/Bestemmingen in apart Tk-proces,
  NSEvent-hotkeys, menubalk-mic, Windows-CI fcntl-skip)

### Changed

- Indicator gesplitst naar package `indicator/` (contract + `_win` / `_mac`)

## [0.1.0] - 2026-07-18

Eerste publieke Windows-release (tag `v0.1.0`).

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

[Unreleased]: https://github.com/benvankruistum/praatMaar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/benvankruistum/praatMaar/releases/tag/v0.1.0
