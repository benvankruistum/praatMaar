# Status — praatMaar

Laatst bijgewerkt: 2026-07-18.

## Ondersteund

| Platform | Status |
|----------|--------|
| Windows 10/11 | Ondersteund (primair doel) |
| macOS | Niet ondersteund — port in onderzoek |
| Linux | Niet ondersteund |

## Werkt op Windows

- Dicteercyclus (opname → Faster-Whisper → klembord/plakken)
- Status-pill zonder focus te stelen (`indicator.py`)
- Systeemvak + instellingen (`tray.py`, `settings.py`)
- Laadscherm met model-downloadvoortgang (`splash.py`)
- Herstel: transcripts + recovery-audio (`recovery.py`)
- Platform-seam: paste, autostart, app-dir, single-instance (`host/`)

## Open / roadmap

1. macOS-port — zie [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
   (indicator no-activate + tray-main-thread zijn de blockers).
2. `dictation.py` opsplitsen (opnamesessie) — genoemd in `CONTEXT.md`.
3. Recovery-audio opruimen / UI.
4. Formele releases / binaries via CI (optioneel).

## Historische handoffs

Sessie-notities (niet langer bron van waarheid):

- [archive/HANDOFF-opname-indicator.md](archive/HANDOFF-opname-indicator.md)
- [archive/HANDOFF-mac-port.md](archive/HANDOFF-mac-port.md)
