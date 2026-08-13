# Windows-release (indie / OSS)

praatMaar wordt gedistribueerd **zonder code signing**. Dat is bewust: geen
Authenticode-certificaat. Gebruikers kunnen een SmartScreen-waarschuwing zien.

macOS-builds: zie [release-macos.md](release-macos.md).

## Versie bijhouden

Houd deze plekken **gelijk** (zonder `v`-prefix, behalve de git-tag):

| Plek | Voorbeeld |
|------|-----------|
| `pyproject.toml` → `version` | `0.6.0` |
| `version_info.txt` (File/ProductVersion) | `0.6.0` / `(0, 6, 0, 0)` |
| `installer/praatMaar.iss` fallback `#define MyAppVersion` | `0.6.0` |
| `scripts/build-windows.ps1` default `-Version` | `0.6.0` |
| Git-tag | `v0.6.0` |
| `CHANGELOG.md` | sectie `[0.6.0] - YYYY-MM-DD`, `[Unreleased]` leegmaken |

Huidige **gepubliceerde** release: **v0.5.0**. Deze branch cut **v0.6.0**
(CHANGELOG-sectie `[0.6.0]`); tag na merge + bevestiging.

### Checklist vóór een tag

1. Versie overal bijgewerkt (tabel hierboven).
2. CHANGELOG: Unreleased → `[x.y.z] - datum`.
3. Tests: `pytest -q`.
4. Tag + push (of handmatige Actions-run).

## Artefacten

Namen volgen de versie, bijv. voor `0.1.0`:

| Bestand | Doel |
|---------|------|
| `praatMaar-Setup-{versie}.exe` | Inno Setup → `%LOCALAPPDATA%\praatMaar\` |
| `praatMaar-{versie}-windows-x64.zip` | Portable: uitpakken en `praatMaar.exe` starten |

Het Whisper-model zit **niet** in de bundle; eerste start downloadt het.

## Lokaal bouwen

1. Dependencies + PyInstaller:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m pip install -e ".[build]"
   ```

2. [Inno Setup 6](https://jrsoftware.org/isinfo.php) installeren (voor de Setup.exe).

3. Alles in één keer (versie expliciet meegeven):

   ```powershell
   .\scripts\build-windows.ps1 -Version 0.6.0
   ```

   Of alleen de app-map:

   ```powershell
   .\scripts\build-windows.ps1 -Version 0.6.0 -SkipInstaller
   ```

Output: `release\` (zip + setup) en `dist\praatMaar\`.
Het build-script geeft `/DMyAppVersion=…` door aan Inno.

De Qt/PySide6-runtime maakt de bundle merkbaar groter dan de vroegere
Tk-gebaseerde UI. Er geldt geen harde groottelimiet; controleer alleen dat de
release-artefacten volledig zijn en functioneel starten.

## GitHub Release

Push een versie-tag; Actions bouwt Windows (`windows-latest`) én macOS
(`macos-14`, Apple Silicon) en zet Setup.exe, Windows-zip én
`praatMaar-*-macos-arm64.zip` op de release-pagina:

```powershell
git tag v0.6.0
git push origin v0.6.0
```

Of: Actions → **Release** → Run workflow (handmatig, vul versie in zonder `v`).

## App-naam in Windows (“Python” i.p.v. praatMaar)

De lijst *Andere pictogrammen op de taakbalk* toont de **FileDescription** van
het draaiende `.exe`. Via `pythonw.exe` is dat altijd “Python”.

De PyInstaller-build zet in `version_info.txt` ProductName/FileDescription op
**praatMaar**. Gebruik dus de Setup.exe of `dist\praatMaar\praatMaar.exe`
(of `start-praatMaar.bat`, die die exe prefereert) om de juiste naam te zien.

Normaal voor unsigned indie-software:

1. **Meer info**
2. **Toch uitvoeren**

Na genoeg downloads kan de reputatie verbeteren; een betaald code-signing
certificaat is de structurele fix (later, optioneel).

## Wat we bewust niet doen (nu)

- Authenticode / `signtool`
- Microsoft Store / MSIX
- macOS signing/notarisatie (macOS zip wel via dezelfde release-workflow; zie
  [release-macos.md](release-macos.md))
