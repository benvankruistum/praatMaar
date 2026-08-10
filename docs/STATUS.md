# Status — praatMaar

Laatst bijgewerkt: 2026-08-10.

**v1.0.0-scope (Accepted):** Windows core-dictation is de primaire belofte;
Meeting Buddy / Local LLM / chunk-transcriptie blijven experimenteel opt-in;
Windows unsigned (SmartScreen documenteren); macOS = vanuit bron / runtime,
geen Gatekeeper-distributiebelofte in 1.0. Zie
[2026-08-01-v1-support-scope-product.md](superpowers/specs/2026-08-01-v1-support-scope-product.md).

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | **Ondersteund (primair)** — Setup/portable (unsigned) |
| macOS Apple Silicon | **Vanuit bron / runtime geverifieerd** — geen signed `.app`-belofte in v1.0 |
| Linux | Experimenteel (X11; AppImage) — zie noot hieronder |

### Linux (experimenteel)

De Qt-UI, host-seam (`host/_linux`: paste via `xdotool`/`ydotool`, XDG-mappen,
flock single-instance, `.desktop`-autostart), systeemvak met venster-fallback,
microfoon-capture (PortAudio) en `xdg-open` voor mappen werken op Linux/**X11**.
Aandachtspunten, nog niet als distributie-build geverifieerd:

- **Wayland:** globale sneltoetsen (pynput) en het niet-focus-stelende overlay
  zijn onbetrouwbaar; gebruik een **X11**-sessie.
- **Klembord:** vereist `xclip`/`xsel` voor pyperclip; anders valt de app terug
  op het Qt-klembord.
- **Meeting Buddy-meetinggeluid** (WASAPI-loopback) is Windows-only; op Linux
  alleen microfoon.

## Werkt op Windows (core / v1.0-belofte)

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Lazy mic-rebind bij dicteerstart / Instellingen-opslaan (device-identiteit;
  geen OS-watcher) — [ADR-0006](adr/0006-mic-lazy-rebind.md)
- Status-pill zonder focus te stelen (`indicator._qt` + Win32 no-activate flags)
- Systeemvak: Instellingen, Bestemmingen, Modules, Help (PySide6-dialogen)
- Meertaligheid UI + spraak (`nl`/`en`/`de`)
- Sticky bestemmingen (transcript naar gekozen map)
- Laadscherm met model-downloadvoortgang (`ui/splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`); beheer + opnieuw
  transcriberen via sectie **Herstel-audio** in Instellingen
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)
- **Modules:** in-process uitbreidingen + event-journal (`modules/`, tray
  **Modules**); inbox-spiegel; optionele incrementele/chunk-transcriptie
  ([ADR-0003](adr/0003-hybrid-module-system.md))
- Windows-release: Inno Setup + CI (gepubliceerd: tag `v0.5.0`; richting
  **v1.0.0** volgens scope-spec hierboven)
- macOS-release: unsigned arm64-zip via dezelfde Release-workflow (`macos-14`)

## Experimentele modules

- `audio-capture`: continue microfooncapture op Windows; Meeting Buddy kan
  optioneel meetinggeluid via WASAPI-loopback mixen (experimenteel)
- `speech-to-text`: incrementele lokale transcriptie via het gedeelde
  Faster-Whisper-model
- `meeting-buddy`: meetingstate, heuristische hints, transcript-stream,
  optionele live-samenvatting, agenda-review (statusladder + vragen van
  anderen) via capability `ai.semantic_analysis`
- `local-llm`: Ollama + Qwen 2.5 als provider van `ai.semantic_analysis`
  (standaard uit; Modules: statuscontrole, installatiehulp, model-download)

Deze Meeting Buddy-MVP is experimenteel. Op Windows neemt Meeting Buddy naast
de microfoon optioneel meetinggeluid op via **WASAPI-loopback** (`pyaudiowpatch`;
standaard uit in defaults, aan te zetten in Eigenschappen). Bluetooth-uitvoer
heeft vaak geen loopback. De overlay toont of loopback actief is; device-keuze
en transcriptmap staan in **Eigenschappen**. Live samenvatting en agenda-review
vereisen module `local-llm` met een klaar Ollama-model (standaard uit;
experimenteel) — zie
[ADR-0004](adr/0004-local-first-inference.md) en
[local-llm design](superpowers/specs/2026-07-23-local-llm-module-design.md).
Zonder Local LLM blijft Meeting Buddy bij heuristische hints. Zie ook het
[MVP-design](superpowers/specs/2026-07-19-meeting-buddy-mvp-design.md) en
[handoff loopback/Teams](HANDOFF-meeting-buddy-teams-loopback.md).
Handmatige Teams-acceptatie (`docs/teams-loopback-acceptance.md`) is nog open —
geen “Teams werkt altijd”-claim in v1.0.

## macOS

Geïmplementeerd én runtime-geverifieerd op Apple Silicon (vanuit bron,
`python dictation.py`):

- `host._mac` — Cmd+V, Application Support, LaunchAgent, flock
- Tray op main thread (`TrayIcon.owns_main_thread` + `run()`)
- Status-pill via gedeelde Qt-HUD (`indicator._qt`; native NSPanel-pad
  historisch ADR-0002 — shipping UI is PySide6)
- Instellingen / Bestemmingen / Modules / Help in-process via PySide6
  ([ADR-0005](adr/0005-ui-toolkit-pyside6.md))
- TCC: Microfoon + Toegankelijkheid verplicht —
  [macos-permissions.md](macos-permissions.md)
- Build-docs: [release-macos.md](release-macos.md), `packaging/macos/entitlements.plist`
- CI-release: unsigned `praatMaar-*-macos-arm64.zip` via `macos-14` in
  `.github/workflows/release.yml` (`scripts/build-macos.sh`)

### Runtime-check (2026-07-18 / 2026-07-19)

Op een echte Mac (arm64), vanuit bron (`python dictation.py` via Cursor):

- [x] App start, model laadt, tray aanwezig
- [x] Toegankelijkheid (`AXIsProcessTrusted`) nodig voor hotkeys
- [x] Dicteercyclus: hotkey → opname → Faster-Whisper → klembord + plakken
- [x] Unit-smoke: host/mac_input/indicator/hotkeys/settings (23 tests)

**Buiten v1.0.0-belofte:** gesigneerde `.app` / Gatekeeper op een schone Mac
(zie roadmap).

## Open / roadmap

1. **Dicteercyclus UX Must** — implementatie op feature-branch (PREPARING,
   non-modal errors, busy, ready-cue); AC-smoke op Windows nog open:
   [ux-states spec](superpowers/specs/2026-08-01-dicteercyclus-ux-states-product.md) ·
   [impl plan](superpowers/plans/2026-08-01-dicteercyclus-ux-states.md).
2. **v1.0.0 uitbrengen** wanneer `/release-readiness` groen is voor Windows
   core (Setup/zip via Actions). macOS unsigned zip zit in dezelfde
   release-workflow; signing/notarisatie later.
   Zie [release-windows.md](release-windows.md) / [release-macos.md](release-macos.md).
3. Meeting Buddy: Teams-loopback-acceptatie afronden vóór eventuele graduation.
4. Experimentele Local LLM + agenda-review: gebruikersvalidatie (blijft
   experimenteel tot dan).

## Historische handoffs

- [HANDOFF-meeting-buddy-teams-loopback.md](HANDOFF-meeting-buddy-teams-loopback.md)
- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
