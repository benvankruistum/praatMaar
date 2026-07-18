# Status — praatMaar

Laatst bijgewerkt: 2026-07-18.

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | Ondersteund (primair doel) |
| macOS | Port in uitvoering — native overlay gekozen (ADR-0002) |
| Linux | Niet ondersteund |

## Werkt op Windows

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Status-pill zonder focus te stelen (`indicator.py`)
- Systeemvak + instellingen (`tray.py`, `settings.py`)
- Laadscherm met model-downloadvoortgang (`splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`)
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)

## Open / roadmap

1. **macOS-port** — beslissing: native overlay-indicator
   ([ADR-0002](adr/0002-macos-native-overlay-indicator.md)).
   Blockers: native pill (`NSPanel`/PyObjC) + tray op main thread.
   Werkpakketten (lokaal ook onder `.scratch/macos-port/`):
   1. `host._mac` op Mac verifiëren (paste, LaunchAgent, singleton)
   2. Tray/menubalk op main thread + Cocoa-runloop
   3. Native overlay-indicator (NSPanel, geen focus-diefstal)
   4. UI-polish (fonts, ⌥⌘-labels, settings-teksten)
   5. TCC-permissies documenteren (+ Info.plist usage strings)
   6. PyInstaller `.app` (arm64) + release-docs
2. Recovery-audio opruimen / UI.
3. Formele releases: tag `v0.1.0` → GitHub Actions bouwt Setup.exe + zip
   (unsigned; zie [release-windows.md](release-windows.md)).

## Historische handoffs

Sessie-notities (niet langer bron van waarheid):

- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
