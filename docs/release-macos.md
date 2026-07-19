# macOS-release (indie / OSS)

praatMaar op macOS bouwt een **`.app`-bundle** met PyInstaller. Code signing en
notarisatie zijn optioneel voor lokale/dev-builds; voor distributie buiten de
Mac van de ontwikkelaar sterk aanbevolen (Gatekeeper).

Zie ook [ADR-0002](adr/0002-macos-native-overlay-indicator.md) (native overlay)
en [macos-permissions.md](macos-permissions.md) (TCC).

Windows-builds: [release-windows.md](release-windows.md).

## Versie

Gebruik dezelfde versiestring als Windows (`pyproject.toml`, CHANGELOG, git-tag).
Huidige gepubliceerde tag: **v0.1.0**. Volgende geplande: **v0.2.0** (nog
Unreleased — macOS-port zit in die lijn).

Zip-naamvoorbeeld:

```bash
VERSION=0.2.0   # gelijk aan pyproject.toml
cd dist && zip -r "praatMaar-${VERSION}-macos-arm64.zip" praatMaar.app
```

Er is nog **geen** automatische GitHub Actions macOS-release; artefacten
handmatig uploaden of later een `macos-latest`-job toevoegen.

## Vereisten op de bouw-Mac

- macOS op Apple Silicon (arm64 eerst; universal2 niet gegarandeerd door CTranslate2)
- Xcode Command Line Tools (of Python van python.org)
- Python 3.10+ (getest: 3.11/3.12)
- Geen PortAudio via brew nodig: `pip install sounddevice` bundelt PortAudio
- Bij Homebrew-Python: ook `brew install python-tk@3.12` (anders
  `No module named '_tkinter'` bij splash/settings)
- Dependencies inclusief PyObjC:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements.txt
  python -m pip install -e ".[build]"
  ```

## Lokaal bouwen

```bash
pyinstaller praatMaar.spec --clean
```

Resultaat: `dist/praatMaar.app`.

Optioneel zippen (versie gelijk aan `pyproject.toml`):

```bash
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
cd dist && zip -r "praatMaar-${VERSION}-macos-arm64.zip" praatMaar.app
```

Het Whisper-model zit **niet** in de bundle; eerste start downloadt het naar
`~/Library/Caches/huggingface` (of de HF-cache van de gebruiker).

## Code signing & notarisatie (later)

1. Apple Developer ID Application-certificaat
2. In `praatMaar.spec`: `codesign_identity="Developer ID Application: …"`
3. Entitlements: `packaging/macos/entitlements.plist`
4. `xcrun notarytool submit …` + `stapler staple`

Zonder signing: rechtsklik → Open bij Gatekeeper-blokkade, of
`xattr -cr dist/praatMaar.app` voor lokale test.

## Vanuit broncode draaien (dev)

```bash
source .venv/bin/activate
python dictation.py
```

Homebrew is optioneel en niet vereist voor PortAudio.

Zet TCC-permissies zoals beschreven in [macos-permissions.md](macos-permissions.md).
Permissies hechten aan de **Terminal** (of IDE) waarmee je start — niet aan een
bundle-id — tot je een `.app` gebruikt.

## Wat we bewust niet doen (nu)

- Cross-compile vanaf Windows/Linux
- Universal2 fat binary
- Mac App Store
- Automatische GitHub Actions macOS-release (kan later op `macos-latest`)
