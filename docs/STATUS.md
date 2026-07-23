# Status — praatMaar

Laatst bijgewerkt: 2026-07-23.

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | Ondersteund (primair doel) |
| macOS | Ondersteund (Apple Silicon; runtime geverifieerd) |
| Linux | Niet ondersteund |

## Werkt op Windows

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Status-pill zonder focus te stelen (`indicator._win`)
- Systeemvak: Instellingen, Bestemmingen, Modules, Help (`tray.py`, dialogen)
- Meertaligheid UI + spraak (`nl`/`en`/`de`)
- Sticky bestemmingen (transcript naar gekozen map)
- Laadscherm met model-downloadvoortgang (`splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`); beheer + opnieuw
  transcriberen via sectie **Herstel-audio** in Instellingen
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)
- **Modules:** in-process uitbreidingen + event-journal (`modules/`, tray **Modules**);
  inbox-spiegel; optionele incrementele transcriptie tijdens opname
  ([ADR-0003](adr/0003-hybrid-module-system.md))
- Windows-release: Inno Setup + CI (gepubliceerd: tag `v0.1.0`)

## Experimentele modules

- `audio-capture`: continue microfooncapture op Windows; Meeting Buddy kan
  optioneel meetinggeluid via WASAPI-loopback mixen (experimenteel)
- `speech-to-text`: incrementele lokale transcriptie via het gedeelde
  Faster-Whisper-model
- `meeting-buddy`: meetingstate, heuristische hints en compacte overlay; staat
  standaard uit en kan via tray **Modules** worden ingeschakeld

Deze Meeting Buddy-MVP is experimenteel. Op Windows neemt Meeting Buddy naast
de microfoon optioneel meetinggeluid op via WASAPI-loopback (standaard aan).
De overlay toont of loopback actief is. Device-keuze voor loopback staat in de
prep-dialoog bij meeting start. Optionele lokale LLM (module `local-llm` +
Meeting Buddy agenda-review) is ontworpen maar nog niet gebouwd — zie
[ADR-0004](adr/0004-local-first-inference.md) en
[local-llm design](superpowers/specs/2026-07-23-local-llm-module-design.md).
Zie ook het [MVP-design](superpowers/specs/2026-07-19-meeting-buddy-mvp-design.md) en
[handoff loopback/Teams](HANDOFF-meeting-buddy-teams-loopback.md).

## macOS

Geïmplementeerd én runtime-geverifieerd op Apple Silicon (macOS 26.x):

- `host._mac` — Cmd+V, Application Support, LaunchAgent, flock
- Tray op main thread (`TrayIcon.owns_main_thread` + `run()`)
- Native overlay-indicator (`indicator._mac`, NSPanel / ADR-0002)
- UI-polish (fonts, Control/Option/Command-labels, settings-teksten)
- Instellingen in apart Tk-proces (voorkomt Cocoa/Tk SIGABRT bij sluiten); idem
  Bestemmingen, Modules en Help
- TCC: Microfoon + Toegankelijkheid verplicht —
  [macos-permissions.md](macos-permissions.md)
- Build-docs: [release-macos.md](release-macos.md), `packaging/macos/entitlements.plist`

### Runtime-check (2026-07-18 / 2026-07-19)

Op een echte Mac (arm64), vanuit bron (`python dictation.py` via Cursor):

- [x] App start, model laadt, tray aanwezig
- [x] Toegankelijkheid (`AXIsProcessTrusted`) nodig voor hotkeys
- [x] Dicteercyclus: hotkey → opname → Faster-Whisper → klembord + plakken
- [x] Unit-smoke: host/mac_input/indicator/hotkeys/settings (23 tests)

Nog niet formeel als distributie-build geverifieerd: gesigneerde `.app` /
Gatekeeper (zie roadmap).

## Open / roadmap

1. Release **v0.2.0**: versie sync + CHANGELOG-cut + Windows-tag (Setup/zip);
   macOS `.app` handmatig of later via CI (signing later).
   Zie [release-windows.md](release-windows.md) / [release-macos.md](release-macos.md).
2. macOS: eventuele Gatekeeper/signing-check op een schone Mac zonder TCC-dev-host.
3. Module **Local LLM** + Meeting Buddy **fase 1** (live samenvatting op
   configureerbare chunks) — daarna coverage per agendapunt en vragenlijst.
   Zie [design](superpowers/specs/2026-07-23-local-llm-module-design.md).

## Historische handoffs

- [HANDOFF-meeting-buddy-teams-loopback.md](HANDOFF-meeting-buddy-teams-loopback.md)
- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
