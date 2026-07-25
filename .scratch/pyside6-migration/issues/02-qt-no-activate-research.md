# Qt no-activate and always-on-top for pill/overlay

Type: research  
Status: resolved  
Blocked by: —

## Question

What does Qt 6 / PySide6 officially support (and what must we do via platform APIs) to implement praatMaar’s **non-activating**, always-on-top **status-pill** and **Meeting Buddy overlay** on **Windows, macOS, and Linux**?

Need facts for:

- Window flags / attributes that avoid stealing focus / activation
- Always-on-top / tool-window behaviour per OS
- Known gaps vs current Tk/Win/Mac indicator seams ([ADR-0002](../../../docs/adr/0002-macos-native-overlay-indicator.md), host indicator contract)
- Practical recommendations for a single code path vs thin per-OS seams

Primary sources only (Qt docs, Qt source/bugs, platform docs). Write findings under `docs/research/` and link from this ticket when done.

## Answer

Shared Qt path (`Tool` + `WindowStaysOnTopHint` + `WindowDoesNotAcceptFocus` + `WA_ShowWithoutActivating`, plus macOS `WA_MacAlwaysShowToolWindow`) covers Windows via `WS_EX_NOACTIVATE`; macOS may still need a thin `nonactivatingPanel` seam (Qt does not set it); Linux X11 is WM-hint-based and Wayland lacks portable overlay placement/no-activate.

Full write-up: [docs/research/qt-no-activate-overlay.md](../../../docs/research/qt-no-activate-overlay.md)
