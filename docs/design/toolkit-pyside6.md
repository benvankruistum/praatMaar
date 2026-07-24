# Toolkit voor vormgeving — PySide6 (Qt)

**Doel-UI-stack:** [PySide6](https://doc.qt.io/qtforpython/) (Qt 6), cross-platform
Windows · macOS · Linux. Designs moeten hierop **bouwbaar** zijn.

Zie ook [fidelity-pass.md](fidelity-pass.md) voor acceptatie.

## Mag Qt

- Standaard OS-titlebar, kaarten, toggles, tabs, primary/ghost knoppen
- Matige radius (4–8 px), accent `#0F6CBD`, badges, statusdots
- Pill/overlay als apart always-on-top venster (geen focus stelen)

## Vermijd / versimpel

| Vermijd | Alternatief |
|---------|-------------|
| Custom titlebar | OS-chrome |
| Zware drop shadow / blur | Lichte border of platte elevatie |
| Web-only layouts | Eén kolom / eenvoudige scroll |
| Pixel-perfect browser fonts via CDN | Segoe / SF / system UI |

## Drie OS’en

Zelfde structuur en tokens; native fonts/chrome mogen verschillen.
