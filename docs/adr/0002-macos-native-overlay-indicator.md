# 0002 — macOS-indicator via native overlay (NSPanel)

- **Status:** Aanvaard
- **Datum:** 2026-07-18
- **Context-term:** indicator (pill) — zie [CONTEXT.md](../../CONTEXT.md)

## Context

De Windows-indicator (`indicator.py`) steunt op tkinter plus een
`WS_EX_NOACTIVATE`-shim. Op macOS werkt die aanpak niet: `-transparentcolor` is
Windows/X11-only, en een niet-activerend venster vereist een native `NSPanel`
met `nonactivatingPanel`. Focus-diefstal breekt auto-paste (Cmd+V) — daarom is
een no-activate-pill op Mac net zo essentieel als op Windows.

Twee strategieën lagen open (zie [HANDOFF-mac-port](../archive/HANDOFF-mac-port.md)):

- **A — Native overlay:** pill behouden via AppKit/`NSPanel` (pyobjc).
- **B — Minimalistisch:** geen pill; alleen menubalk + notificatie.

De gebruiker koos **optie A** (2026-07-18): de Mac-versie moet hetzelfde
gedrag en gevoel hebben als Windows.

ADR-0001 liet het indicator-venster bewust buiten de `host`-seam: dat is een
GUI-toolkit-gebonden seam, geen goedkope OS-op.

## Beslissing

Op macOS bouwen we de indicator als **native overlay**:

- Een `NSPanel` (of equivalent) met `NSWindowStyleMask.nonactivatingPanel`, zodat
  de pill nooit de focus / key window steelt van het actieve invoerveld.
- Implementatie via **PyObjC** (AppKit), niet via tkinter-venstertrucjes.
- De bestaande toestanden en API van de dicteercyclus blijven leidend:
  `RecordingState` (idle / recording / transcribing / cancelled / error),
  waveform tijdens opname, transient cancelled/error, geen focus-diefstal.
- Windows behoudt de huidige tkinter + `WS_EX_NOACTIVATE`-implementatie.
- De gemeenschappelijke contractkant (toestanden, callbacks naar de
  dicteercyclus) blijft gedeeld; de venstertechniek is per OS.

### Bewust buiten deze ADR

- Tray/menubalk-threading (pystray op main thread op macOS) — apart werkpakket,
  maar wel een harde dependency voor een draaiende Mac-app.
- Code signing / notarisatie / TCC-plists — release-werk, niet indicator-ontwerp.

## Alternatieven overwogen

- **Optie B — geen pill.** Verworpen: andere UX dan Windows; gebruiker wil
  pariteit.
- **tkinter + hack om activatie te onderdrukken.** Verworpen: geen betrouwbare
  `nonactivatingPanel`-equivalent; focus-diefstal blijft een risico voor paste.
- **Indicator in de `host`-seam stoppen.** Verworpen (zelfde reden als ADR-0001):
  trekt Cocoa/tkinter-complexiteit in een seam die voor paste/autostart bedoeld
  is. Liever een dunne indicator-seam of OS-specifieke modules naast een gedeeld
  contract.

## Gevolgen

- Extra dependency op macOS: `pyobjc-framework-Cocoa` (of gerichte PyObjC-wheels).
- Indicator-code splitst of krijgt een Mac-pad: Windows blijft ctypes/tkinter;
  Mac wordt AppKit/`NSPanel`.
- Acceptatiecriterium op Mac: tijdens opname/transcriberen blijft het
  voorgrondvenster (bijv. Notes/TextEdit) key; Cmd+V plakt in dat veld.
- Blocking voor de rest van de Mac-port: zonder deze pill (of een tijdelijke
  stub) is de dicteercyclus op Mac niet productiewaardig volgens de gekozen UX.
