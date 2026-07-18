# macOS-permissies (TCC)

Zonder deze drie toestemmingen faalt praatMaar vaak **stil** (geen hotkey, geen
mic, geen plakken).

| Permissie | Waarom | Waar in Systeeminstellingen |
|-----------|--------|-----------------------------|
| **Microfoon** | Opname via sounddevice | Privacy en beveiliging → Microfoon |
| **Input Monitoring** | Globale events (sommige macOS-versies) | Privacy en beveiliging → Invoercontrole |
| **Accessibility** | Globale sneltoets (NSEvent) + Cmd+V (Quartz) | Privacy en beveiliging → Toegankelijkheid |

## Dev (vanuit bron / Terminal)

Permissies hechten aan de host-app:

- Terminal.app / iTerm
- of de Cursor/VS Code-integrated terminal

Zet de drie toggles aan voor die host. Herstart de host-app na de eerste grant
als de hotkey nog niet werkt.

**Toegankelijkheid is verplicht** voor de globale sneltoets (NSEvent-monitor).
Zonder die toggle start de app wel, maar hoort ze geen hotkeys.

### macOS 26+ (Tahoe)

Apple dwingt af dat TSM/HIToolbox alleen op de main thread mag. `pynput` doet
dat vanaf een achtergrondthread en **crasht** (SIGTRAP). praatMaar gebruikt
daarom op Mac `mac_input.QuartzKeyListener` (AppKit) i.p.v. pynput.

Instellingen draait in een **apart Tk-proces** (`settings_process.py`). Een
tkinter-dialoog in dezelfde Cocoa-runloop als pystray/NSApp crasht bij sluiten
(`PyEval_RestoreThread` → SIGABRT).

Sneltoets-opname in Instellingen gebruikt Tk KeyPress (niet alleen NSEvent-
keycodes), zodat **Windows-/PC-toetsenborden** (Win-toets = Command, Alt,
pijltjes, ISO-`<>`) wél geregistreerd worden. De dicteer-hotkey zelf luistert
via `QuartzKeyListener` met dezelfde tokens (modifiers uit `modifierFlags`).

## `.app`-bundle

In `praatMaar.spec` staat `NSMicrophoneUsageDescription` in de Info.plist zodat
macOS een microfoon-prompt kan tonen. Input Monitoring en Accessibility blijven
handmatige toggles (geen usage-string-prompt zoals bij de mic).

Na code signing hechten permissies stabiel aan de bundle-identifier
`nl.wulf.praatmaar`.
