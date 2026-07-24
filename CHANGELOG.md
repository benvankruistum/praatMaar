# Changelog

Alle noemenswaardige wijzigingen aan dit project worden hier bijgehouden.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en dit project volgt [SemVer](https://semver.org/lang/nl/).

## [Unreleased]

### Added

### Changed

### Fixed

## [0.2.0] - 2026-07-24

### Added

- **Meeting Buddy (experimenteel, Windows):** tray-cascade (starten/stoppen),
  agenda-bibliotheek met recente Markdown-agenda’s, eigenschappen voor
  loopback/uitvoerapparaat/transcriptmap; loopback-status in overlay;
  automatische reconnect bij device-wissel; configureerbare mix-gewichten
- Streaming Markdown-meetingjournal (definitieve transcriptdelen + checklist)
  met padmelding bij stoppen
- **Local LLM**-module (standaard uit): lokale Ollama/Qwen-provider voor
  `ai.semantic_analysis`, met statuscontrole, installatiehulp en model-download
- Live samenvatting, agenda-review (statusladder) en vragen van anderen in de
  Meeting Buddy-overlay (vereist Local LLM; standaard uit in Eigenschappen)
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
- **Module-capabilities:** acties (Modules-dialoog + optioneel tray), shutdown-hook,
  `ui_dispatch`, per-module `config.json` onder app-dir
- **SharedWhisper:** modules delen het geladen Faster-Whisper-model (+ lock) via
  `ModuleContext.whisper` — geen tweede model-load naast dicteren
- **Capability registry:** modules bieden services aan via stabiele ID’s
  (`ctx.capabilities`); providers o.a. Speaker Detection en Local LLM
  (`ai.semantic_analysis`)
- **Meeting Buddy MVP (experimenteel):** continue capture, incrementele lokale
  transcriptie, immutable meetingstate en heuristische hints; `meeting-buddy`
  staat standaard uit
- Per bestemming optioneel automatisch plakken (`auto_paste`, default uit)
- macOS-port: native NSPanel-indicator (`indicator._mac`, ADR-0002), tray op
  main thread, `host._mac`, TCC- en release-docs, PyObjC-dependency op Darwin
- Ruff lint/format als CI-guardrail
- Cursor project-skills: `/update-documentation` en `/prepare-release`
  (`.cursor/skills/`; zie `CLAUDE.md`)

### Changed

- Tray toont module-acties (Meeting Buddy, Local LLM) als root-cascades
- Incrementele transcriptie toont voortgang; bij stoppen wordt de laatste
  partial als eindtekst gebruikt wanneer beschikbaar
- Instellingen, bestemmingen en status-pill verbeterd (tabs, meetingmodus)
- Indicator gesplitst naar package `indicator/` (contract + `_win` / `_mac`)
- Live samenvatting / agenda-review volgen de UI-taal (nl/en/de)

### Fixed

- Store-Python/AppData-paden correct opgelost voor Explorer en gebruikersdata
- Meeting Buddy blijft responsief tijdens doorlopende transcriptie;
  stop-/capture-races robuuster
- Agenda-review filtert vragen van de host (`SpeakerRole.ME`) strenger
- Heuristische topic-hints blijven actief als Local LLM-review uit staat
- Warme microfoonstream heropent na Bluetooth disconnect/reconnect
- Hotkey-/settings-/splash-labels platform-aware (Mac: Control/Option/Command)
- Diverse macOS-stabiliteitsfixes (settings/Bestemmingen in apart Tk-proces,
  NSEvent-hotkeys, menubalk-mic, Windows-CI fcntl-skip)

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

[Unreleased]: https://github.com/benvankruistum/praatMaar/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/benvankruistum/praatMaar/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/benvankruistum/praatMaar/releases/tag/v0.1.0
