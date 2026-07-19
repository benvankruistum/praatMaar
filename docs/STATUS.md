# Status — praatMaar

Laatst bijgewerkt: 2026-07-19.

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | Ondersteund (primair doel) |
| macOS | Ondersteund (Apple Silicon; runtime geverifieerd) |
| Linux | Niet ondersteund |

## Werkt op Windows

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Status-pill zonder focus te stelen (`indicator._win`)
- Systeemvak: Instellingen, Bestemmingen, Help (`tray.py`, dialogen)
- Meertaligheid UI + spraak (`nl`/`en`/`de`)
- Sticky bestemmingen (transcript naar gekozen map)
- Laadscherm met model-downloadvoortgang (`splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`); beheer + opnieuw
  transcriberen via sectie **Herstel-audio** in Instellingen
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)
- Windows-release: Inno Setup + CI (gepubliceerd: tag `v0.1.0`)

## macOS

Geïmplementeerd én runtime-geverifieerd op Apple Silicon (macOS 26.x):

- `host._mac` — Cmd+V, Application Support, LaunchAgent, flock
- Tray op main thread (`TrayIcon.owns_main_thread` + `run()`)
- Native overlay-indicator (`indicator._mac`, NSPanel / ADR-0002)
- UI-polish (fonts, Control/Option/Command-labels, settings-teksten)
- Instellingen in apart Tk-proces (voorkomt Cocoa/Tk SIGABRT bij sluiten)
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

## Historische handoffs

- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
