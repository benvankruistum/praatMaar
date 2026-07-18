# Windows-release (indie / OSS)

praatMaar wordt gedistribueerd **zonder code signing**. Dat is bewust: geen
Authenticode-certificaat, geen Apple-notarization. Gebruikers kunnen een
SmartScreen-waarschuwing zien.

## Artefacten

| Bestand | Doel |
|---------|------|
| `praatMaar-Setup-0.1.0.exe` | Inno Setup-installer → `%LOCALAPPDATA%\praatMaar\` |
| `praatMaar-0.1.0-windows-x64.zip` | Portable: uitpakken en `praatMaar.exe` starten |

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

3. Alles in één keer:

   ```powershell
   .\scripts\build-windows.ps1
   ```

   Of alleen de app-map:

   ```powershell
   .\scripts\build-windows.ps1 -SkipInstaller
   ```

Output: `release\` (zip + setup) en `dist\praatMaar\`.

## GitHub Release

Push een versie-tag; de workflow `.github/workflows/release.yml` bouwt op
`windows-latest` en hangt de artefacts aan de release:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

Houd `MyAppVersion` in `installer/praatMaar.iss`, `version` in `pyproject.toml`
en de tag in sync.

## SmartScreen (“Windows beschermde je pc”)

Normaal voor unsigned indie-software:

1. **Meer info**
2. **Toch uitvoeren**

Na genoeg downloads kan de reputatie verbeteren; een betaald code-signing
certificaat is de structurele fix (later, optioneel).

## Wat we bewust niet doen (nu)

- Authenticode / `signtool`
- Apple Developer ID / notarization (geen Mac-build)
- Microsoft Store / MSIX
