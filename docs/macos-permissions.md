# macOS-permissies (TCC)

Zonder deze drie toestemmingen faalt praatMaar vaak **stil** (geen hotkey, geen
mic, geen plakken).

| Permissie | Waarom | Waar in Systeeminstellingen |
|-----------|--------|-----------------------------|
| **Microfoon** | Opname via sounddevice | Privacy en beveiliging → Microfoon |
| **Input Monitoring** | Globale sneltoets (pynput listener) | Privacy en beveiliging → Invoercontrole |
| **Accessibility** | Cmd+V sturen (pynput/pyautogui) | Privacy en beveiliging → Toegankelijkheid |

## Dev (vanuit bron / Terminal)

Permissies hechten aan de host-app:

- Terminal.app / iTerm
- of de Cursor/VS Code-integrated terminal

Zet de drie toggles aan voor die host. Herstart de host-app na de eerste grant
als de hotkey nog niet werkt.

## `.app`-bundle

In `praatMaar.spec` staat `NSMicrophoneUsageDescription` in de Info.plist zodat
macOS een microfoon-prompt kan tonen. Input Monitoring en Accessibility blijven
handmatige toggles (geen usage-string-prompt zoals bij de mic).

Na code signing hechten permissies stabiel aan de bundle-identifier
`nl.wulf.praatmaar`.
