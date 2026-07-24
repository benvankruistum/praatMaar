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

- [Qt no-activate and always-on-top for pill/overlay](issues/02-qt-no-activate-research.md) — Shared Qt Tool/no-focus/on-top flags; Win maps to WS_EX_NOACTIVATE; Mac may need thin nonactivatingPanel seam; Wayland overlay placement best-effort

## Not yet specified

- Exact **QSS / token extraction** from the updated canvas (colors, radii, type) vs briefs when they diverge.
- How the **module host** exposes Qt dialogs/overlays without coupling module logic to widgets.
- **macOS notarization / entitlements** and **Linux package formats** (AppImage vs deb vs flatpak) beyond “CI builds something”.
- Whether Meeting Buddy **overlay** and status-**pill** share one Qt window stack or stay separate top-levels.
- CI matrix details (which Linux distros / display servers to gate releases on).

## Out of scope

- Rewriting transcription, Local LLM, or Meeting Buddy **business logic** (only UI host/surfaces).
- WebView / Electron / CustomTkinter as UI path.
- Further **Tk theme polish** as a product goal (Tk is interim only until Qt ships).
- Pixel-perfect browser fidelity beyond toolkit-pyside6 constraints.
