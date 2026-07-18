# praatMaar

Lokale, Nederlandstalige dicteertool voor **Windows**. Neemt spraak op via een
sneltoets, transcribeert lokaal met [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)
(geen cloud-API) en plakt de tekst in het actieve invoerveld.

> **Platform:** alleen Windows wordt ondersteund. macOS staat op de roadmap
> (`docs/STATUS.md`); de app start daar nu niet.

## Vereisten

- Windows 10/11
- Python **3.10+** (getest tot 3.13)
- Microfoon + microfoontoegang in Windows-privacyinstellingen
- Eerste start: internet om het Whisper-model te downloaden (daarna offline)

## Installatie

```powershell
git clone https://github.com/benvankruistum/praatMaar.git
cd praatMaar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Starten

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
gedownload naar `%USERPROFILE%\.cache\huggingface`. Daarna: systeemvak-icoon
+ status-pill.

### Bediening (standaard)

| Actie | Sneltoets |
|--------|-----------|
| Start/stop dicteren (toggle) | `Ctrl+Shift+Alt+Spatie` |
| Annuleren tijdens opname | `Esc` |
| Instellingen / afsluiten | Rechtsklik systeemvak-icoon |

Sneltoets, modus (toggle of push-to-talk), microfoon en model zijn aanpasbaar
via **Instellingen** in het systeemvak-menu.

## Privacy

- Transcriptie gebeurt **lokaal** op je CPU; audio gaat niet naar een
  cloud-API.
- Bij de **eerste** (of bij modelwissel) wordt het Whisper-model gedownload van
  Hugging Face.
- De app gebruikt een **globale sneltoets** (pynput) en kan tekst op het
  **klembord** zetten en plakken (`Ctrl+V`).
- Gebruikersdata onder `%APPDATA%\praatMaar\`:
  - `config.json` — instellingen
  - `transcripts\` — recente transcripts (max. 50)
  - `recovery\` — audio van mislukte transcripties (niet automatisch opgeruimd)
  - `praatMaar.log` — diagnostisch logbestand

Zie ook [SECURITY.md](SECURITY.md).

## Logs bij problemen

Als “er niets gebeurt” (vaak bij `pythonw` / gebouwde exe): open

`%APPDATA%\praatMaar\praatMaar.log`

## Builden (optioneel)

PyInstaller onedir, windowed:

```powershell
python -m pip install -e ".[build]"
.\.venv\Scripts\pyinstaller.exe praatMaar.spec --clean
```

Resultaat: `dist\praatMaar\praatMaar.exe`. Het model wordt **niet** meegebundeld.

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
