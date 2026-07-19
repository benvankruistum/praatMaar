# Status — praatMaar

Laatst bijgewerkt: 2026-07-19.

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | Ondersteund (primair doel) |
| macOS | Port geïmplementeerd — op een Mac verifiëren |
| Linux | Niet ondersteund |

## Werkt op Windows

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Status-pill zonder focus te stelen (`indicator._win`)
- Systeemvak: Instellingen, Bestemmingen, Help (`tray.py`, dialogen)
- Meertaligheid UI + spraak (`nl`/`en`/`de`)
- Sticky bestemmingen (transcript naar gekozen map)
- Laadscherm met model-downloadvoortgang (`splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`)
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)
- Windows-release: Inno Setup + CI (gepubliceerd: tag `v0.1.0`)

## macOS (nieuw)

Geïmplementeerd (code); runtime-verificatie op een Mac staat nog open:

- `host._mac` — Cmd+V, Application Support, LaunchAgent, flock
- Tray op main thread (`TrayIcon.owns_main_thread` + `run()`)
- Native overlay-indicator (`indicator._mac`, NSPanel / ADR-0002)
- UI-polish (fonts, Control/Option/Command-labels, settings-teksten)
- Instellingen in apart Tk-proces (voorkomt Cocoa/Tk SIGABRT bij sluiten)
- TCC-docs: [macos-permissions.md](macos-permissions.md)
- Build-docs: [release-macos.md](release-macos.md), `packaging/macos/entitlements.plist`

Handmatige checklist op de Mac: zie [release-macos.md](release-macos.md) +
permissies-doc. Eerste prioriteit: dicteercyclus + geen focus-diefstal + paste.

## Open / roadmap

1. macOS runtime-verificatie + eventuele fixes na eerste Mac-run.
2. Recovery-audio opruimen / UI.
3. Release **v0.2.0**: versie sync + CHANGELOG-cut + Windows-tag (Setup/zip);
   macOS `.app` handmatig of later via CI (signing later).
   Zie [release-windows.md](release-windows.md) / [release-macos.md](release-macos.md).

## Historische handoffs

- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
