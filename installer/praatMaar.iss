; Inno Setup script voor praatMaar (indie / OSS, zonder code signing).
;
; Vereisten:
;   1. Eerst PyInstaller:  pyinstaller praatMaar.spec --clean
;   2. Inno Setup 6:       https://jrsoftware.org/isinfo.php
;   3. Compileren:         iscc installer\praatMaar.iss
;
; Of:  .\scripts\build-windows.ps1 -Version x.y.z
;
; Output: installer\Output\praatMaar-Setup-{MyAppVersion}.exe
; Fallback MyAppVersion = laatste gepubliceerde default; sync bij release
; (zie docs/release-windows.md).

#define MyAppName "praatMaar"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#define MyAppPublisher "Ben van Kruistum"
#define MyAppURL "https://github.com/benvankruistum/praatMaar"
#define MyAppExeName "praatMaar.exe"
; Houd MyAppVersion gelijk aan pyproject.toml en de git-tag (zonder "v").
#define DistDir "..\dist\praatMaar"

[Setup]
AppId={{A7E3C2B1-9F4D-4E8A-B6C0-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=praatMaar-Setup-{#MyAppVersion}
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; Geen Authenticode: indie/OSS — SmartScreen kan waarschuwen (zie README).
; SignTool=...  ; later, als er een certificaat is

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Snelkoppeling op het bureaublad"; GroupDescription: "Extra snelkoppelingen:"; Flags: unchecked

[Files]
; Hele PyInstaller-onedir-map
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Deïnstalleren {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Laat %APPDATA%\praatMaar (config, transcripts, logs) bewust staan.
Type: filesandordirs; Name: "{app}"
