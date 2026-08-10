# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-buildscript voor praatMaar (onedir, windowed).

Windows:  .venv\\Scripts\\pyinstaller.exe praatMaar.spec --clean
          → dist\\praatMaar\\praatMaar.exe

macOS:    .venv/bin/pyinstaller praatMaar.spec --clean
          → dist/praatMaar.app  (BUNDLE, alleen op Darwin)

Het Whisper-model wordt NIET meegebundeld: het wordt bij de eerste start
(eenmalig) gedownload naar de HuggingFace-cache van de gebruiker.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


def _project_version() -> str:
    """Lees project.version uit pyproject.toml (fallback voor oudere Python)."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    path = Path("pyproject.toml")
    with path.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


try:
    _VERSION = _project_version()
except Exception:
    _VERSION = "0.0.0"

datas = [
    ("locales", "locales"),
    ("docs/user", "docs/user"),
    ("modules/defaults", "modules/defaults"),
]
binaries = []
hiddenimports = []

# Pakketten met native DLL's, databestanden of dynamisch geladen backends die
# PyInstaller niet vanzelf volledig meepakt. collect_all haalt van elk de
# submodules, datafiles én binaries op.
_COLLECT = [
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "av",
    "tokenizers",
    "sounddevice",
    "pynput",
    "huggingface_hub",
    "PySide6",
    "ui",
    "ui.dialogs",
]

if sys.platform == "win32":
    # WASAPI loopback (Meeting Buddy); PortAudio-DLL + submodules.
    _COLLECT.append("pyaudiowpatch")

if sys.platform == "darwin":
    _COLLECT.append("objc")
    _COLLECT.append("AppKit")
    _COLLECT.append("Foundation")
    _COLLECT.append("Quartz")

for _pkg in _COLLECT:
    try:
        _d, _b, _h = collect_all(_pkg)
    except Exception:
        continue
    datas += _d
    binaries += _b
    hiddenimports += _h

hiddenimports += [
    "app_logging",
    "config",
    "destinations",
    "destinations_dialog",
    "help_dialog",
    "recovery",
    "settings",
    "splash",
    "tray",
    "ui.app",
    "ui.dialogs.destinations",
    "ui.dialogs.help",
    "ui.dialogs.message",
    "ui.dialogs.modules",
    "ui.dialogs.settings",
    "ui.marshal",
    "ui.splash",
    "ui.tray",
    "indicator",
    "indicator._contract",
    "indicator._qt",
    "hotkeys",
    "opnamesessie",
    "win_identity",
    "i18n",
    "modules",
    "modules._builtin.audio_capture",
    "modules._builtin.wasapi_loopback",
    "modules._builtin.speech_to_text",
    "modules._builtin.meeting_buddy",
    "modules.capabilities",
    # Platform-seam: de adapters worden lazy (in host._select) geïmporteerd,
    # dus expliciet opnemen zodat ze zeker in de bundle zitten.
    "host",
    "host._win",
    "host._mac",
    "host._linux",
]


a = Analysis(
    ["dictation.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "tensorflow",
        "matplotlib",
        "pandas",
        "IPython",
        "notebook",
        "ipywidgets",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="praatMaar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=(
        "packaging/macos/entitlements.plist" if sys.platform == "darwin" else None
    ),
    # FileDescription/ProductName → "praatMaar" i.p.v. generieke bootloader-naam
    # in Windows-taakbalkhoek / systeempictogrammen-lijst.
    version="version_info.txt" if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="praatMaar",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="praatMaar.app",
        icon=None,
        bundle_identifier="nl.wulf.praatmaar",
        info_plist={
            "CFBundleName": "praatMaar",
            "CFBundleDisplayName": "praatMaar",
            "CFBundleShortVersionString": _VERSION,
            "CFBundleVersion": _VERSION,
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": (
                "praatMaar heeft microfoontoegang nodig om spraak op te nemen "
                "voor lokale transcriptie."
            ),
            "NSAppleEventsUsageDescription": (
                "praatMaar stuurt plak-toetsen naar het actieve invoerveld."
            ),
        },
    )
