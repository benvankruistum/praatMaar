# macOS-permissies (TCC)

Zonder deze drie toestemmingen faalt praatMaar vaak **stil** (geen hotkey, geen
mic, geen plakken).

| Permissie | Waarom | Waar in Systeeminstellingen |
|-----------|--------|-----------------------------|
| **Microfoon** | Opname via sounddevice | Privacy en beveiliging → Microfoon |

Tijdens een opname toont macOS soms een **extra** systeembrede mic-indicator
in de menubalk (privacy). Dat is niet een tweede praatMaar. Buiten opnames houdt
praatMaar de mic-stream **dicht** op Mac, zodat die systeemicoon weg blijft.
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
daarom op Mac `mac_input.QuartzKeyListener` (AppKit/NSEvent) i.p.v. pynput.

Instellingen draait **in-process** via PySide6 (`ui/dialogs/settings.py`).

Sneltoets-opname in Instellingen gebruikt dezelfde globale listener als dicteren
(NSEvent-tokens). Zonder actieve listener valt opname terug op Qt KeyPress
(handig als je alleen in het instellingenvenster test).

## `.app`-bundle

In `praatMaar.spec` staat `NSMicrophoneUsageDescription` in de Info.plist zodat
macOS een microfoon-prompt kan tonen. Input Monitoring en Accessibility blijven
handmatige toggles (geen usage-string-prompt zoals bij de mic).

Na code signing hechten permissies stabiel aan de bundle-identifier
`nl.wulf.praatmaar`.
