# macOS-release (indie / OSS)

praatMaar op macOS bouwt een **`.app`-bundle** met PyInstaller. Code signing en
notarisatie zijn optioneel voor lokale/dev-builds; voor distributie buiten de
Mac van de ontwikkelaar sterk aanbevolen (Gatekeeper).

Zie ook [ADR-0002](adr/0002-macos-native-overlay-indicator.md) (native overlay)
en [macos-permissions.md](macos-permissions.md) (TCC).

Windows-builds: [release-windows.md](release-windows.md).

## Versie

Gebruik dezelfde versiestring als Windows (`pyproject.toml`, CHANGELOG, git-tag).
Huidige gepubliceerde tag: **v0.3.0**. Cut op deze lijn: **v0.4.0**
(CHANGELOG-sectie; macOS-port zit in die release).

Zip-naamvoorbeeld:

```bash
VERSION=0.4.0   # gelijk aan pyproject.toml
cd dist && zip -r "praatMaar-${VERSION}-macos-arm64.zip" praatMaar.app
```

Automatische release: bij tag `v*` bouwt `.github/workflows/release.yml` op
`macos-14` (Apple Silicon) een unsigned `praatMaar-*-macos-arm64.zip` en uploadt
die samen met de Windows-artefacten naar de GitHub Release. Lokaal bouwen blijft
mogelijk via `scripts/build-macos.sh`.

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

Aanbevolen (PyInstaller + zip onder `release/`):

```bash
chmod +x scripts/build-macos.sh
./scripts/build-macos.sh          # versie uit pyproject.toml
# of: ./scripts/build-macos.sh 0.4.0
```

Handmatig:

```bash
pyinstaller praatMaar.spec --clean
```

Resultaat: `dist/praatMaar.app` (en via het script:
`release/praatMaar-<versie>-macos-arm64.zip` op Apple Silicon).

De Qt/PySide6-runtime maakt de `.app` merkbaar groter dan de vroegere
Tk-gebaseerde UI. Er geldt geen harde groottelimiet; controleer alleen dat de
bundle volledig is en functioneel start.

`CFBundleShortVersionString` / `CFBundleVersion` komen uit `pyproject.toml`
(via `praatMaar.spec`).

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
- Universal2 fat binary / Intel (`macos-13`) CI-artefact
- Mac App Store
- Code signing / notarisatie in CI (Apple Developer ID secrets)
