# 0005 — PySide6 as the shipped UI toolkit

- **Status:** Aanvaard
- **Datum:** 2026-07-24
- **Context-term:** UI shell — zie [CONTEXT.md](../../CONTEXT.md)

## Context

praatMaar's Tk UI and the macOS-native status pill do not provide one
maintainable UI path for Windows, macOS, and Linux. The product needs a tray,
dialogs, a status pill, and Meeting Buddy overlays while retaining local
transcription and the existing `host.Host` platform seam.

## Beslissing

praatMaar ships its product UI with **PySide6 (Qt 6)**.

1. A single `QApplication` owns the in-process UI event loop.
2. UI work from worker threads is marshalled to Qt's main thread through the
   existing `UiDispatch` callable contract.
3. The status pill and Meeting Buddy overlay are separate always-on-top Qt
   top-level widgets.
4. `host.Host` remains responsible for OS-specific non-UI capabilities such as
   paste, autostart, app directories, and single-instance handling.
5. Windows, macOS, and Linux are in scope. Linux tray support is best effort;
   a non-tray fallback must remain available where the desktop environment does
   not expose a system tray.
6. Tk and Qt must not be mixed in a shipped release. Tk facades may remain only
   during the migration until the Qt cutover is complete.

## Alternatieven overwogen

- **Tkinter behouden.** Verworpen: insufficient for the cross-platform tray,
  overlays, and maintainable native UI surface required by the migration.
- **Een web UI (Electron/WebView).** Verworpen: adds a second runtime and does
  not fit the local Python desktop application's existing seams.
- **Platform-specifieke UI's.** Verworpen: duplicates feature work and makes
  three-platform parity impractical.

## Gevolgen

- PySide6 becomes a runtime dependency and is bundled by release tooling.
- UI modules use QSS theme tokens instead of Tk styling.
- Linux needs a minimal `Host` adapter before Linux support is claimed.
- Native OS adapters may still be added narrowly where Qt cannot provide
  no-activation behaviour, especially on macOS.
