# Wayfinder: PySide6 three-platform UI

Labels: `wayfinder:map`

## Destination

The way to ship praatMaar's product UI on **PySide6 (Qt 6)** for **Windows, macOS, and Linux** is clear: no open architectural or product decisions remain that would block implementing and releasing a canvas-faithful Qt UI (within [toolkit-pyside6.md](../../docs/design/toolkit-pyside6.md) constraints), with **Tk retired** as the UI runtime. Canvas source of truth: [docs/design/canvas/praatMaar-ui.dc.html](../../docs/design/canvas/praatMaar-ui.dc.html) (synced from updated Meeting Buddy export).

## Notes

- **Domain:** [CONTEXT.md](../../CONTEXT.md), [docs/agents/domain.md](../../docs/agents/domain.md), [ADR-0005](../../docs/adr/0005-ui-toolkit-pyside6.md) (toolkit already accepted).
- **Design:** [docs/design/](../../docs/design/) briefs + canvas; toolkit constraints are binding.
- **Skills each session:** `/grilling`, `/domain-modeling`; `/research` / `/prototype` when a ticket says so.
- **Plan, then hand off:** tickets resolve **decisions** (and research facts). When the frontier is empty, hand off to an implementation plan / build — do not treat build slices as wayfinder tickets unless Notes are redrawn.
- **Already locked outside this map:** PySide6 is the toolkit (ADR-0005); three OS’en in destination scope (user chose full parity).

## Decisions so far

<!-- index — one line per closed ticket -->

- [Migration cutover shape](issues/01-migration-cutover-shape.md) — Full rewrite on branch/flag; flip when Win+Mac+Linux meet the bar; no mixed Tk+Qt in shipped builds
- [Qt no-activate and always-on-top for pill/overlay](issues/02-qt-no-activate-research.md) — Shared Qt Tool/no-focus/on-top flags; Win maps to WS_EX_NOACTIVATE; Mac may need thin nonactivatingPanel seam; Wayland overlay placement best-effort
- [Linux system tray with PySide6](issues/03-linux-tray-research.md) — `QSystemTrayIcon` / StatusNotifierItem; stock GNOME needs a non-tray fallback (host is DE/extension, not app-packaged)
- [Three-platform packaging and release bar](issues/04-packaging-release-bar.md) — Linux AppImage only; tray best-effort + fallback; Win CI as now, Mac/Linux manual; no size cap
- [Design fidelity bar vs canvas](issues/05-design-fidelity-bar.md) — Toolkit hard; canvas layout/spacing/colors exact; native chrome/fonts only; live-app sign-off — see `docs/design/fidelity-pass.md`
- [Process model: tray, hotkeys, Qt event loop](issues/06-process-event-loop.md) — One QApplication; workers + marshal to main; Qt for UI, host/generic seams (+ thin OS adapters) for the rest

## Not yet specified

- Exact **QSS / token extraction** from the canvas during implementation (build detail, not a product fork).
- Concrete **module-host** wiring for Qt dialogs/overlays (keep module logic widget-free; shell owns Qt) — detail for the implementation plan.
- Whether pill and Meeting Buddy overlay are **two top-level** Qt windows or one stack — default unless plan says otherwise: **separate** always-on-top top-levels (matches toolkit brief).

## Out of scope

- Rewriting transcription, Local LLM, or Meeting Buddy **business logic** (only UI host/surfaces).
- WebView / Electron / CustomTkinter as UI path.
- Further **Tk theme polish** as a product goal (Tk is interim only until Qt ships).
- Pixel-perfect browser fidelity beyond toolkit-pyside6 constraints.
- Linux **deb/Flatpak** and automated Mac/Linux release CI (until real users warrant it).
