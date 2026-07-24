<#
.SYNOPSIS
  Build Windows release (indie / OSS).

.DESCRIPTION
  Bouwt de PyInstaller-onedir-map, optioneel een Inno Setup-installer, en een
  portable zip. Geen code signing (bewust — zie docs/release-windows.md).

.PARAMETER SkipInstaller
  Sla Inno Setup over; alleen dist + zip.

.PARAMETER SkipZip
  Geen portable zip maken.

.PARAMETER Version
  Versiestring in bestandsnamen. Houd gelijk aan pyproject.toml / git-tag
  (zonder "v"). Zie docs/release-windows.md. Voorbeeld: 0.2.0
#>

param(
    [switch]$SkipInstaller,
    [switch]$SkipZip,
    [string]$Version = "0.2.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $PyInstaller)) {
    $PyInstaller = "pyinstaller"
}

Write-Host "==> PyInstaller (praatMaar.spec)"
& $PyInstaller praatMaar.spec --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller mislukt ($LASTEXITCODE)" }

$Dist = Join-Path $Root "dist\praatMaar"
if (-not (Test-Path (Join-Path $Dist "praatMaar.exe"))) {
    throw "Geen dist\praatMaar\praatMaar.exe gevonden."
}

$ReleaseDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

if (-not $SkipZip) {
    $ZipPath = Join-Path $ReleaseDir "praatMaar-$Version-windows-x64.zip"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Write-Host "==> Portable zip: $ZipPath"
    Compress-Archive -Path (Join-Path $Dist "*") -DestinationPath $ZipPath -Force
}

if (-not $SkipInstaller) {
    $Iscc = $null
    foreach ($candidate in @(
            "iscc",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        )) {
        if ($candidate -eq "iscc") {
            $cmd = Get-Command iscc -ErrorAction SilentlyContinue
            if ($cmd) { $Iscc = $cmd.Source; break }
        }
        elseif (Test-Path $candidate) {
            $Iscc = $candidate
            break
        }
    }

    if (-not $Iscc) {
        $msg = "Inno Setup (ISCC.exe) niet gevonden. Installeer: https://jrsoftware.org/isinfo.php"
        if ($env:CI -eq "true") {
            throw $msg
        }
        Write-Warning "$msg — sla installer over."
    }
    else {
        Write-Host "==> Inno Setup: $Iscc"
        & $Iscc "/DMyAppVersion=$Version" (Join-Path $Root "installer\praatMaar.iss")
        if ($LASTEXITCODE -ne 0) { throw "ISCC mislukt ($LASTEXITCODE)" }

        $Setup = Join-Path $Root "installer\Output\praatMaar-Setup-$Version.exe"
        if (-not (Test-Path $Setup)) {
            throw "Installer niet gevonden: $Setup"
        }
        Copy-Item $Setup -Destination $ReleaseDir -Force
        Write-Host "==> Installer gekopieerd naar release\"
    }
}

Write-Host ""
Write-Host "Klaar. Artefacten in: $ReleaseDir"
Get-ChildItem $ReleaseDir | Format-Table Name, Length -AutoSize
