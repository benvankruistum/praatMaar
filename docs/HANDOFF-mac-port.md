# Handoff — praatMaar naar macOS porten

Geschreven 2026-07-17. Werktaal: **Nederlands**. Doel: een verse agent kan hiermee
naadloos verder met het onderzoek naar draaien/bouwen van praatMaar op een Mac.

> Bewaard in `docs/`. Gaat over de macOS-port; de verouderde `HANDOFF.md` in de root
> gaat nog over de (afgeronde) opname-indicator.

> **Update 2026-07-17 — platform-seam gebouwd (op Windows).** De architectuur-review
> (`/improve-codebase-architecture`) leverde een `host`-seam op: `host/__init__.py`
> (`Host`-Protocol + `sys.platform`-selectie), `host/_win.py` (absorbeert het vroegere
> `autostart.py`) en `host/_mac.py`. Daarmee zijn de blockers **paste**, **autostart**
> en **config-dir** uit deze handoff nú achter één seam gebracht en gedrag-behoudend
> geverifieerd op Windows. De term staat in `CONTEXT.md`. **Resterend Mac-werk voor deze
> drie:** `host/_mac.py` verifiëren — `paste`/`app_dir` zijn compleet, de LaunchAgent
> (`set_autostart`) is nog ongetest op een Mac. De **indicator** en het **threading-model**
> hieronder bleven bewust buiten scope en zijn nog steeds het grote werk.

## Context van deze sessie

De gebruiker heeft een MacBook en wil onderzoeken wat er nodig is om praatMaar
(nu Windows-only) op macOS te draaien en te bouwen. Deze sessie was **analyse-only**:
er is **geen code gewijzigd** en er is nog **geen ADR/spec** geschreven. De bevindingen
hieronder staan nog in geen enkel artifact — dit document is de enige vastlegging tot
nu toe.

## Wat is onderzocht (codebase-scan)

De transcriptiekern is platform-neutraal; het probleem zit in de UI-/OS-integratielaag.
Portabiliteitsoordeel per module (bronbestanden in de rep-root):

- ✅ **Werkt op Mac:** `dictation.py` (transcriptie via Faster-Whisper/CTranslate2, CPU
  int8 — draait ook op Apple Silicon), `recovery.py` (puur stdlib).
- 🟡 **Klein werk:** `config.py` (val terug op `~/Library/Application Support/` i.p.v.
  `%APPDATA%`), `hotkeys.py` (Alt=Option, cmd=Command; labels Mac-conform maken),
  `splash.py` (tkinter werkt; lettertype "Segoe UI" → systeemfont), `settings.py`
  (teksten + Toplevel-gedrag Mac-conform).
- 🔴 **Blocker / herbouw:**
  - **Plakken** — `dictation.py:736` gebruikt `pyautogui.hotkey("ctrl", "v")`; op Mac
    moet dat `cmd+v` zijn, anders werkt auto-paste niet.
  - **`autostart.py`** — volledig `winreg` (Run-key). Mac-equivalent = LaunchAgent
    (`~/Library/LaunchAgents/*.plist`). Aparte implementatie nodig.
  - **`tray.py`** — pystray heeft een macOS-backend, maar `run_detached()` op een eigen
    thread werkt daar niet: het menubalk-item moet op de main thread + Cocoa-runloop.
  - **`indicator.py`** — grootste blok. Gooit `SystemExit` als niet `win32`. Gebruikt
    `ctypes.windll.user32` + `WS_EX_NOACTIVATE`. Techniek én ontwerp moeten opnieuw.

## De twee echt lastige punten

1. **Pill mag geen focus stelen.** Op Windows regelt de `WS_EX_NOACTIVATE`-shim dat
   (zie `indicator.py` §"WINDOWS API"). Op macOS: `-transparentcolor` wordt niet
   ondersteund (Windows/X11-only), en een niet-activerend venster vereist een native
   `NSPanel` met `nonactivatingPanel`-stijl — kan tkinter niet. Focus-diefstal breekt
   auto-paste, dus dit is essentieel.
2. **Threading-model botst.** Nu: tkinter-mainloop (main thread) + pystray detached +
   pynput-listener. Op macOS eisen zowel AppKit (menubalk) als tkinter de
   main-thread-runloop op → die opzet werkt niet zoals nu.

## macOS-permissies (TCC) — sowieso nodig

- **Microfoon** (vereist `NSMicrophoneUsageDescription`, anders geen prompt).
- **Input Monitoring** — zodat pynput de globale sneltoets hóórt.
- **Accessibility** — zodat pynput toetsen stúurt (de `cmd+v`).

Zonder deze drie faalt de app stil. Ze hechten netjes aan een gesigneerde app-bundle;
bij draaien-vanuit-broncode hechten ze aan de terminal (rommelig).

## Bouwen & distribueren

- PyInstaller `.app` kan alleen **ón een Mac** (geen cross-compile vanaf Windows).
- Apple Silicon: bouw arm64 (universal2 lastig — CTranslate2-wheels leveren dat vaak niet).
- Voor soepele permissies: code signing + notarisatie + stabiele bundle-identifier.
  De `.spec` (`praatMaar.spec`) heeft nu `codesign_identity=None` /
  `entitlements_file=None` — voor Mac in te vullen.

## Openstaande beslissing (hét vertrekpunt voor de volgende sessie)

**Indicator-strategie op Mac** — nog niet gekozen:
- **Optie A — Native overlay (pyobjc):** meeste werk, behoudt gedrag (geen
  focus-diefstal, mooie pill). Aanbevolen als de Mac-versie even goed moet voelen.
- **Optie B — Minimalistisch:** pill vervalt op Mac; alleen menubalk + systeemnotificatie
  bij start/stop. Veel minder werk, andere UX.

De gebruiker heeft hier nog niet op geantwoord. Vraag dit als eerste uit.

## Concrete voorbereidingen (nog te doen, op de Mac)

1. **Reproduceerbare omgeving:** er is **geen `requirements.txt`/`pyproject.toml`** in de
   repo (alleen `.venv`). Eerst dependencies vastleggen (bijv. `pip freeze` op Windows).
2. **Mac-systeemvereisten:** Xcode CLT, Homebrew, Python 3.11/3.12, `brew install portaudio`.
3. **Platform-abstractielaag** introduceren: OS-specifiek werk (autostart, indicator-venster,
   tray-threading, plak-toets) achter een kleine interface met `_win`/`_mac`-implementaties.
4. **Indicator-strategie kiezen** (zie hierboven) — bepaalt de omvang van het werk.

## Housekeeping / let op

- **`HANDOFF.md` in de repo-root is verouderd:** die gaat volledig over de opname-indicator
  (afgerond op 2026-07-15) en niet over het Mac-werk. Openstaand punt: nieuwe handoff die
  overschrijven, of het Mac-werk als apart document (`HANDOFF-mac.md`)? Nog te beslissen.
- **Geen git-repo** (lokale map). Windows 11, PowerShell primair. Python `.venv` = 3.13.
- **GUI-apps starten:** niet via de Bash-tool (landt op onzichtbaar bureaublad) — via
  PowerShell/terminal. Zie geheugen `gui-launch-via-powershell`.
- Het echte bouwen/testen gebeurt op de MacBook van de gebruiker; de agent op Windows kan
  begeleiden maar niet zelf op Mac bouwen.

## Suggested skills (voor de volgende agent)

- **`grill-with-docs`** — de indicator-beslissing (Optie A vs B) en de nieuwe
  Mac-terminologie stress-testen tegen het domeinmodel, en meteen `CONTEXT.md` / een ADR
  onder `docs/adr/` bijwerken (het project gebruikt de single-context + ADR-conventie;
  zie `docs/agents/domain.md`).
- **`to-issues`** (of Matt Pococks `to-tickets`) — het portingplan opknippen in
  onafhankelijk oppakbare tickets onder `.scratch/<feature-slug>/`, conform
  `docs/agents/issue-tracker.md`.
- **`/handoff`** (Matt Pocock, handmatig) — aan het eind van de volgende sessie opnieuw.
