# Designbriefs — praatMaar UI

Briefs voor een vormgever + goedgekeurde canvas-mockups. Huidige UI is
functioneel (Tk/ttk); briefs beschrijven **wat**, de canvas toont **hoe**.

## Briefs

| Brief | Focus |
|-------|--------|
| [pill.md](pill.md) | Status-capsule (dicteercyclus) |
| [settings.md](settings.md) | Instellingen (tabs) |
| [destinations.md](destinations.md) | Bestemmingen-beheer |
| [modules.md](modules.md) | Modules-dialoog (aan/uit + acties) |
| [meeting-buddy.md](meeting-buddy.md) | Meeting Buddy overlay + dialogen |

## Canvas (vormgeving)

Open lokaal in een browser (HTML + `support.js`):

- [canvas/praatMaar-ui.dc.html](canvas/praatMaar-ui.dc.html) — alle surfaces in één
  document (ankers `#1a` Meeting Buddy · `#2a` pill · `#3a` Bestemmingen ·
  `#4a` Instellingen · `#5a` Modules)

## Implementatie

- [fidelity-pass.md](fidelity-pass.md) — **actieve opdracht:** canvas exact (checklists + acceptatie)
- [implementation-plan.md](implementation-plan.md) — PySide6-migratieplan (verwijst door)
- [toolkit-pyside6.md](toolkit-pyside6.md) — wat Qt wel/niet mag

**Merkfamilie:** Segoe UI / Windows 11-licht, accent `#0F6CBD`, gedeelde
radius/knoppen/iconografie; verschillende vormfactoren (capsule / dialoog /
overlay).

**Platform:** Windows · macOS · Linux. UI-talen: nl / en / de.
