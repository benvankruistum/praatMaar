# Linux-release (manual / AppImage)

Linux-builds zijn voorlopig handmatig en worden als **AppImage** verspreid. Er
is geen Linux-job in GitHub Actions en we bouwen geen deb- of Flatpak-pakket
tot daar gebruikersvraag voor is.

## Vereisten op de buildmachine

- Een recente x86_64-Linuxdistributie; bouw op een zo oud mogelijke ondersteunde
  basis om de glibc-compatibiliteit van de AppImage ruim te houden.
- Python 3.10+ en een virtuele omgeving.
- De reguliere buildafhankelijkheden plus
  [appimagetool](https://docs.appimage.org/packaging-guide/from-source/native-binaries.html).
- Een werkende grafische sessie voor de live-smoke-test; de build zelf is
  PyInstaller `onedir`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e ".[build]"
```

## Handmatige build

1. Maak de PyInstaller-map:

   ```bash
   pyinstaller praatMaar.spec --clean
   ```

   Dit maakt `dist/praatMaar/`. Het Whisper-model zit niet in de bundle; de
   eerste start downloadt het naar de Hugging Face-cache van de gebruiker.

2. Maak een `AppDir` met die map als hoofdprogramma. Voeg een
   `praatMaar.desktop`, een passend `praatMaar.png`-icoon en een `AppRun`
   launcher toe. `AppRun` start `usr/bin/praatMaar` (de gekopieerde PyInstaller
   executable) en zet zo nodig de werkmap op de AppImage-locatie.

3. Bouw en test het artefact:

   ```bash
   appimagetool AppDir praatMaar-<versie>-linux-x86_64.AppImage
   chmod +x praatMaar-<versie>-linux-x86_64.AppImage
   ./praatMaar-<versie>-linux-x86_64.AppImage
   ```

4. Verifieer in een Linux-desktopsessie de tray of de fallback, Instellingen,
   Bestemmingen, Modules, Help en een korte dicteercyclus voordat het artefact
   wordt geüpload.

## Tray is best-effort

De Qt-tray gebruikt een StatusNotifierItem-host van de desktopomgeving. KDE en
veel distributies met een AppIndicator/SNI-extensie tonen het icoon; een
ongewijzigde GNOME Shell kan dat niet doen. praatMaar moet daarom ook zonder
tray bruikbaar blijven via het fallbackvenster en de daarin beschikbare menu-
acties. Verpak geen tray-host en maak `libappindicator` geen harde dependency.

Gebruikers op GNOME zonder icoon kunnen desgewenst een door hun distributie
geleverde AppIndicator/SNI-extensie installeren. Dit is geen voorwaarde om de
AppImage te starten.

## Wat we bewust niet doen (nu)

- deb-, rpm- of Flatpak-pakketten
- Geautomatiseerde Linux-releases of signing
- Een gegarandeerde tray op elke desktopomgeving of Wayland-compositor
