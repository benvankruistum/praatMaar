# 0001 — Platform-seam (`host`) voor OS-afhankelijke operaties

- **Status:** Aanvaard
- **Datum:** 2026-07-17
- **Context-term:** platform-seam (`host`) — zie [CONTEXT.md](../../CONTEXT.md)

## Context

De app was volledig op Windows gebouwd. Kennis van het besturingssysteem lag
verspreid: de plak-toets in `dictation.py` (`pyautogui.hotkey("ctrl", "v")`), het
automatisch meestarten in een eigen `autostart.py` (`winreg`), en de datamap in
`config.py` (`%APPDATA%`). Het no-activate indicator-venster in `indicator.py`
(`ctypes`/`WS_EX_NOACTIVATE`) hoort ook tot die categorie.

Aanleiding was het onderzoek naar een macOS-port (zie
[docs/HANDOFF-mac-port.md](../HANDOFF-mac-port.md)): er was geen enkele plek om een
tweede besturingssysteem achter te hangen. Een Mac-adapter toevoegen betekende
edits in vier modules. De OS-afhankelijkheid had geen naam en geen testoppervlak.

## Beslissing

Eén module — `host` — waarachter alle OS-afhankelijke operaties zitten die de app
nodig heeft. Vorm: een `Host`-Protocol met per besturingssysteem één instantie,
gekozen op `sys.platform`.

- **Interface:** `paste()`, `set_autostart()`, `is_autostart_enabled()`,
  `app_dir()`, `acquire_single_instance()`.
- **Adapters:** `host._win` (Windows; absorbeert het vroegere `autostart.py`
  volledig — `winreg` + launch-command) en `host._mac` (macOS).
- **Selectie:** `host.default`, gekozen op `sys.platform`; niet-ondersteund
  platform → `RuntimeError` bij selectie.
- De module heet `host`, niet `platform` — dat laatste zou de stdlib schaduwen.

Adapters importeren hun zware/OS-specifieke libraries (pyautogui, winreg) pas in
de methode-aanroep, zodat `default = _select()` licht blijft (draait al bij import,
vóór het laadscherm).

### Bewust buiten scope

Het no-activate **indicator-venster** valt buiten deze seam. Dat is een ander soort
seam — verweven met de GUI-toolkit (tkinter, straks Cocoa) — en verdient een eigen
deepening. Deze seam beperkt zich tot de goedkope, stateless OS-ops die door
meerdere modules gedeeld worden.

## Alternatieven overwogen

- **Ook het indicator-venster in de seam.** Verworpen: trekt de tkinter/Cocoa-
  venstercomplexiteit erbij, maakt de eerste seam groot en traag te bewijzen.
- **Kale module met functies die op `sys.platform` vertakt.** Verworpen: niet
  substitueerbaar. Het Protocol met een per-OS instantie maakt de seam een echt
  testoppervlak — een `FakeHost` is injecteerbaar waar code een `Host` verwacht.

## Gevolgen

- Alle OS-isms voor paste/autostart/config-dir zitten op één plek (locality).
- Eén interface, meerdere call sites (leverage); `config.py`/`recovery.py` zijn
  pure consumenten van `app_dir()`.
- De Mac-port van deze drie operaties = "vul `host._mac` in", niet "doorzoek de
  boom". `paste`/`app_dir` zijn compleet; de LaunchAgent (`set_autostart`) is nog
  ongetest op een Mac.
- Twee adapters (Windows + macOS) bewijzen dat de seam echt is, geen hypothese.
- `autostart.py` is verwijderd (geabsorbeerd). De PyInstaller-spec neemt de
  `host`-modules nu expliciet mee.

## Aanvulling (2026-07-17) — single-instance

`acquire_single_instance()` toegevoegd aan de seam: een tweede start (autostart én
handmatig, of dubbelklik) moet géén tweede listener/tray/indicator opleveren.
`WinHost` gebruikt een named mutex (sessie-lokaal, per gebruiker), `MacHost` een
`flock` op een lockbestand in `app_dir()`. Beide grendels worden door het OS
vrijgegeven zodra het proces stopt — geen stale-lock. `dictation.py` roept de
grendel als eerste in `main()` aan, vóór splash en model. Cross-proces
geverifieerd op Windows (tweede instantie krijgt `False` en stopt).

## Verificatie (2026-07-17, op Windows)

Gedrag-behoudend geverifieerd: `py_compile` op alle modules, en een runtime
import-smoketest (`host.default` = `WinHost`, `app_dir()`/`config_dir()` →
`%APPDATA%\praatMaar`, autostart-read tegen het echte register). De
schrijfpaden `paste()` en `set_autostart()` zijn niet afgevuurd — die zitten in de
gebruikers-acceptatietest.
