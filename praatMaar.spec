# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-buildscript voor praatMaar (onedir, windowed).

Bouwen:  .venv\\Scripts\\pyinstaller.exe praatMaar.spec --clean
Resultaat: dist\\praatMaar\\praatMaar.exe

Het Whisper-model wordt NIET meegebundeld: het wordt bij de eerste start
(eenmalig) gedownload naar de HuggingFace-cache van de gebruiker
(%USERPROFILE%\\.cache\\huggingface). Daar is het laadscherm voor.
"""

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Pakketten met native DLL's, databestanden of dynamisch geladen backends die
# PyInstaller niet vanzelf volledig meepakt. collect_all haalt van elk de
# submodules, datafiles én binaries op.
_COLLECT = [
    "faster_whisper",   # assets/silero_vad_v6.onnx (VAD)
    "ctranslate2",      # native inferentie-DLL's
    "onnxruntime",      # native DLL's voor het VAD-model
    "av",               # PyAV: audio decoderen (native DLL's)
    "tokenizers",       # native .pyd, gebruikt door faster_whisper
    "sounddevice",      # PortAudio-DLL (_sounddevice_data)
    "pynput",           # toetsenbord-backend wordt dynamisch geladen
    "pystray",          # systeemvak-backend wordt dynamisch geladen
    "huggingface_hub",  # veel lazy imports voor de download
]

for _pkg in _COLLECT:
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Lokale modules die pas lazy (binnen functies) geïmporteerd worden; expliciet
# opnemen zodat ze zeker in de bundle zitten.
hiddenimports += [
    "config",
    "recovery",
    "settings",
    "splash",
    "tray",
    "indicator",
    "hotkeys",
    # Platform-seam: de adapters worden lazy (in host._select) geïmporteerd,
    # dus expliciet opnemen zodat ze zeker in de bundle zitten.
    "host",
    "host._win",
    "host._mac",
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
        # Niet gebruikt; scheelt fors in omvang en buildtijd.
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
    console=False,          # windowed, net als pythonw (geen console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
