# Changelog

Alle noemenswaardige wijzigingen aan dit project worden hier bijgehouden.

Het formaat is gebaseerd op [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/),
en dit project volgt [SemVer](https://semver.org/lang/nl/).

## [Unreleased]

### Added

- **Dicteerpresets** in Instellingen → Geavanceerd: Snel / Gebalanceerd /
  Nauwkeurig zetten model + veilige beam/VAD-defaults (geen systeemsmeting)
  ([spec](docs/superpowers/specs/2026-08-11-dictation-presets-product.md)).
- **Composition-root strangler (ADR-0007):** package `app/` (`AppRuntime`,
  settings, hotkey router, run/startup) en `dicteercyclus/` (Opnamesessie-
  façade + mic/incremental/delivery); dunne `dictation.py`-entry; geen
  import-time sessie.

### Changed

- **Privacy:** console/log print geen volle transcripttekst meer (alleen
  lengte); `SECURITY.md` documenteert optionele Local LLM / Ollama.
- **Meeting Buddy stop:** dictation-pill/hotkey stopt alleen de dicteercyclus;
  MB heeft eigen overlay/tray-stop.
- **macOS paste:** Quartz ⌘V weer achter `host` (`host/_mac_paste.py`) na
  verwijdering van root-`mac_input`.

### Fixed

## [0.6.0] - 2026-08-10

### Added

- **Recente transcripts in het systeemvak:** cascade met de laatste vijf
  geslaagde dicteer-transcripts (datum/tijd); klik zet de tekst opnieuw op het
  klembord (geen auto-plak)
  ([spec](docs/superpowers/specs/2026-08-10-recent-transcripts-tray-product.md)).
- **Whisper-tab in Instellingen:** beam size, VAD (aan/uit + min. stilte),
  voortbouwen op vorige tekst, geen-spraak-drempel, initial prompt en hotwords —
  live toepasbaar zonder herstart
  ([spec](docs/superpowers/specs/2026-08-08-whisper-settings-tab-product.md)).

### Changed

- **Pill-transcriptie-voortgang is hybride:** tijdens de finale Whisper-run
  beweegt de balk op een tijdschatting (audio × RTF) en trekt omhoog bij
  segment-voortgang — geen lange stilstand op `0%`
  ([spec](docs/superpowers/specs/2026-08-10-hybrid-transcription-progress-design.md)).

### Fixed

## [0.5.0] - 2026-08-10

### Added

- **macOS-release via GitHub Actions:** bij tag `v*` bouwt CI op Apple Silicon
  (`macos-14`) een unsigned `praatMaar-*-macos-arm64.zip` en publiceert die
  samen met de Windows Setup/zip. Lokaal: `scripts/build-macos.sh`.
  Gatekeeper: rechtsklik → Open, of `xattr -cr praatMaar.app`
  ([docs/release-macos.md](docs/release-macos.md)).

### Fixed

- **Warme microfoon volgt headset/default opnieuw:** bij start van de
  dicteercyclus (en na mic-wijziging in Instellingen) heropent praatMaar de
  stream alleen als de PortAudio device-identiteit is gewijzigd — geen app-
  herstart meer nodig na Bluetooth verbinden terwijl de app al draaide
  ([ADR-0006](docs/adr/0006-mic-lazy-rebind.md)).

## [0.4.0] - 2026-08-03

### Added

- **Meetinggeluid werkt echt** (Windows): Meeting Buddy neemt het gekozen
  uitvoerapparaat op via WASAPI-loopback (`pyaudiowpatch`) in plaats van de
  niet-werkende sounddevice-loopback of een "Stereo Mix" die op moderne
  Windows-installaties vrijwel altijd ontbreekt.
- **Spreker-onderscheid met één microfoon:** deelnemers worden als `spk_1`,
  `spk_2`, … in het meetingtranscript gemarkeerd.
- **Aparte geluidsbalkjes per bron** in de Meeting Buddy-overlay: je ziet of het
  van de microfoon of van het meetinggeluid komt.
- **Chunk-transcriptie** voor incrementele transcriptie: audio wordt in stukken
  verwerkt op stilte of een tijdvenster, met LED-indicatie in de status-pill.
- **Duidelijker dicteercyclus:** de pill toont "Voorbereiden…" zolang de
  microfoon opengaat (geen valse "Opname" meer), meldt fouten zonder het
  actieve venster te stelen, en geeft na het starten kort "Klaar om op te nemen".
- **Status-pill vernieuwd** conform het canvas-voorstel: looptijd tijdens
  opname, gevulde stopknop, voortgangsbalk met percentage bij transcriberen,
  sneltoets als losse toetsvakjes, een "Opnieuw"-knop bij een mislukte opname,
  en een klikbare modus-tag om tussen toggle en push-to-talk te wisselen.
- **Live samenvatting als bullets:** 3–5 punten, gevoed met alleen het nieuwe
  transcript sinds de vorige ronde, en weggeschreven als sectie
  `## Samenvatting` in het meeting-`.md`.
- **v1.0.0 support-scope** vastgelegd (Windows als kern; Meeting Buddy en Local
  LLM experimenteel; macOS vanuit broncode) —
  [spec](docs/superpowers/specs/2026-08-01-v1-support-scope-product.md).

### Changed

- Documentatie (STATUS, README, Help, SECURITY, CONTEXT, ADR-0003 en de
  locales) afgestemd op de Qt-UI, het journal zonder transcripttekst en de
  v1.0-platformmatrix.
- De status-pill verbruikt minder energie: in rust wordt niet meer geschilderd
  en zakt de pollfrequentie van 20 naar 4 keer per seconde.

### Fixed

- **Sneltoets bleef "hangen":** na gebruik van bijvoorbeeld Shift+Esc kon
  daarna alléén Shift de opname starten. De app controleert nu bij Windows of
  de toetsen echt ingedrukt zijn in plaats van te vertrouwen op de eigen
  administratie, en ruimt achtergebleven toetsen op.
- Hetzelfde probleem zorgde ervoor dat plakken tot 3 seconden kon wachten; die
  vertraging is weg.
- De app blijft licht van kleur wanneer Windows in donkere modus staat.
- Openstaande dialogen worden bij sluiten volledig vrijgegeven, en "map openen"
  meldt een fout in plaats van stil te falen bij een offline netwerkmap.

## [0.3.0] - 2026-07-28

### Added

- **Local LLM-eigenschappen:** keuze tussen standaard Ollama
  (`127.0.0.1:11434` + `qwen2.5:7b`) of een eigen Ollama-endpoint (basis-URL +
  model) via Modules → Local LLM → Eigenschappen.
- **PySide6 (Qt 6) UI** voor Windows, macOS en Linux; de Tk-UI is
  uitgefaseerd ([ADR-0005](docs/adr/0005-ui-toolkit-pyside6.md)).
- **Canvas-fidelity** voor alle schermen: status-pill (states P1–P6),
  Bestemmingen, Instellingen, Modules en Meeting Buddy (overlay + Agenda-
  en Eigenschappen-dialoog), conform `docs/design/canvas/`.
- **Meeting Buddy live-samenvatting tweekoloms:** met samenvatting aan
  groeit de overlay naar 600 px met een eigen samenvatting-kolom (losse
  punten + Kopiëren); geminimaliseerd toont de overlay een donkere mini-pill.
- Gedeelde UI-componenten en -tokens in `ui/theme.py` / `ui/widgets.py`
  (`ToggleSwitch`, `FlowLayout`, checkbox-vinkje, radio-stip, combobox-chevron).
- Subtiele waarschuwing voor gedeelde/onveilige mappen bij Bestemmingen.
- **Linux (experimenteel, X11/AppImage):** host-seam (paste, XDG, autostart,
  single-instance), systeemvak met venster-fallback, `xdg-open` voor mappen
  en een Qt-klembord-fallback.

### Changed

- Alle dialogen, de pill en de overlay volgen de canvas-designtokens; native
  OS-titelbalk en systeemfonts zijn de enige bewuste afwijkingen.

### Fixed

- De tray-app sluit niet meer af wanneer een dialoog wordt gesloten.
- De status-pill sluit netjes bij het stoppen van een meeting.
- Modules-kaarten worden niet meer afgekapt bij scrollen; actieknoppen
  wrappen naar een tweede regel en de primaire knop is weer zichtbaar.
- Overlay-rijen worden bij elke her-render correct vrijgegeven (geen
  widget-ophoping tijdens een meeting).
- **Incrementele transcriptie:** bij stop altijd een finale Whisper-run over de
  hele buffer (niet langer de laatste partial als eindtekst). Voorkomt dat het
  eindstuk ontbreekt wanneer de buffer groeit en partials achterlopen.
- **Meeting Buddy / continuous STT:** bij stop wordt de capture-buffer geflusht
  en de STT-wachtrij leeggedraaid (geen discard meer), zodat het eindstuk van
  een meeting niet stil verdwijnt.
- **Meeting stoppen liep vast:** het stoppen van een meeting kon de app
  blokkeren (eerst circa twee minuten geen reactie, daarna vastlopen) doordat
  de stop op de laatste transcriptie wachtte terwijl die op de stop wachtte.
- **Privacy/AVG:** transcript-inhoud wordt niet meer meegeschreven in het
  event-journal (`events/events.jsonl` houdt alleen de tekstlengte bij) en het
  logbestand `praatMaar.log` roteert boven 5 MB. Beide groeiden voorheen
  onbeperkt, buiten de retentie die voor transcripts al gold.
- **Sneltoets opnemen** werkt betrouwbaar: de opgenomen combinatie kon eerder
  toetsen bevatten die nooit konden afgaan, en het opnemen kon de app laten
  crashen.
- Het tray-icoon en de status-pill worden altijd vanaf de juiste thread
  bijgewerkt; op systemen zónder systeemvak start de app nu zonder crash.
- **Meeting Buddy:** de overlay komt niet meer terug nadat een meeting is
  gestopt; opnieuw verbinden houdt de gekozen spraaktaal aan; open vragen uit
  de Local LLM-analyse leveren nu daadwerkelijk een hint op.
- **Meetinggeluid:** levert de meetinggeluid-bron niets, dan valt de opname
  netjes terug op alleen de microfoon (voorheen kon het transcript leeg blijven
  en liep het geheugengebruik op).
- **Local LLM:** statuscontroles wachten maximaal 5 seconden, zodat een
  onbereikbaar endpoint het opstarten en de vensters niet meer laat bevriezen.
- Een onbekende modelnaam in `config.json` valt terug op `small` in plaats van
  een mislukte start.
- Windows: de controle op "app draait al" is betrouwbaarder; macOS/Linux tonen
  weer het PID van de draaiende instantie.
- Opgenomen audio blijft niet meer in de tijdelijke map achter wanneer het
  bewaren voor herstel mislukt.
- Dialogen worden bij sluiten volledig vrijgegeven (geen geheugenopbouw bij
  herhaald openen), en "map openen" meldt nu een fout in plaats van stil te
  falen bij een offline netwerkmap.

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

[Unreleased]: https://github.com/benvankruistum/praatMaar/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/benvankruistum/praatMaar/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/benvankruistum/praatMaar/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/benvankruistum/praatMaar/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/benvankruistum/praatMaar/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/benvankruistum/praatMaar/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/benvankruistum/praatMaar/releases/tag/v0.1.0
