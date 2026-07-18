# praatMaar

Lokale, Nederlandstalige dicteertool. Neemt spraak op via een sneltoets,
transcribeert lokaal met [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)
(geen cloud-API) en plakt de tekst in het actieve invoerveld.

> **Platform:** Windows 10/11 is primair ondersteund. **macOS** heeft een
> native overlay-port (NSPanel); runtime-verificatie op een Mac staat nog open —
> zie [docs/STATUS.md](docs/STATUS.md).

## Vereisten

### Windows

- Windows 10/11
- Python **3.10+** (getest tot 3.13)
- Microfoon + microfoontoegang in Windows-privacyinstellingen
- Eerste start: internet om het Whisper-model te downloaden (daarna offline)

### macOS

- macOS op Apple Silicon (arm64)
- Python **3.10+**, Xcode CLT, Homebrew `portaudio`
- TCC: Microfoon, Input Monitoring, Toegankelijkheid —
  [docs/macos-permissions.md](docs/macos-permissions.md)
- Eerste start: internet voor model-download

## Installatie

### Kant-en-klare build (Windows, aanbevolen)

Download de nieuwste release op
[GitHub Releases](https://github.com/benvankruistum/praatMaar/releases):

- **Setup** (`praatMaar-Setup-*.exe`) — installeert naar `%LOCALAPPDATA%\praatMaar`
- **Portable zip** — uitpakken en `praatMaar.exe` starten

Builds zijn **niet digitaal ondertekend** (indie/OSS). Als Windows waarschuwt
(“Windows beschermde je pc”): **Meer info** → **Toch uitvoeren**.

Details: [docs/release-windows.md](docs/release-windows.md).

### Vanuit broncode (Windows)

```powershell
git clone https://github.com/benvankruistum/praatMaar.git
cd praatMaar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Vanuit broncode (macOS)

```bash
brew install portaudio
git clone https://github.com/benvankruistum/praatMaar.git
cd praatMaar
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python dictation.py
```

Zet daarna de TCC-permissies (zie hierboven). Build: [docs/release-macos.md](docs/release-macos.md).

## Starten (Windows)

Met console (handig bij problemen):

```powershell
.\.venv\Scripts\python.exe dictation.py
```

Zonder consolevenster (achtergrond):

```powershell
.\start-praatMaar.bat
```

Of dubbelklik `start-praatMaar.vbs` (stil, geen zwarte cmd-flash).

Bij de eerste start verschijnt een laadscherm terwijl het model wordt
gedownload. Daarna: systeemvak-/menubalk-icoon + status-pill.

### Bediening (standaard)

| Actie | Sneltoets |
|--------|-----------|
| Start/stop dicteren (toggle) | `Ctrl+Shift+Alt+Spatie` (op Mac: Control+Shift+Option+Spatie) |
| Annuleren tijdens opname | `Esc` |
| Instellingen / Bestemmingen / Help / afsluiten | Rechtsklik systeemvak-icoon (Mac: menubalk) |

Sneltoets, modus (toggle of push-to-talk), microfoon en model zijn aanpasbaar
via **Instellingen** in het systeemvak-menu. **Bestemmingen** beheren sticky
opslagmappen (naam + pad; wisselen met stem via exacte naam). **Help** opent
lokale gebruikersdocumentatie (nl/en/de).

## Privacy

- Transcriptie gebeurt **lokaal** op je CPU; audio gaat niet naar een
  cloud-API.
- Bij de **eerste** (of bij modelwissel) wordt het Whisper-model gedownload van
  Hugging Face.
- De app gebruikt een **globale sneltoets** (pynput) en kan tekst op het
  **klembord** zetten en plakken (Ctrl+V / Cmd+V).
- Gebruikersdata:
  - Windows: `%APPDATA%\praatMaar\`
  - macOS: `~/Library/Application Support/praatMaar/`
  - `config.json`, `transcripts\`, `recovery\`, `praatMaar.log`

Zie ook [SECURITY.md](SECURITY.md).

## Logs bij problemen

- Windows: `%APPDATA%\praatMaar\praatMaar.log`
- macOS: `~/Library/Application Support/praatMaar/praatMaar.log`

## Builden / release (optioneel)

- Windows: [docs/release-windows.md](docs/release-windows.md)
- macOS: [docs/release-macos.md](docs/release-macos.md)

```text
pyinstaller praatMaar.spec --clean
```

Het model wordt **niet** meegebundeld.

## Ontwikkeling

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Architectuurtermen: [CONTEXT.md](CONTEXT.md). Beslissingen: [docs/adr/](docs/adr/).
Huidige status / roadmap: [docs/STATUS.md](docs/STATUS.md).
Bijdragen: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licentie

[MIT](LICENSE)
