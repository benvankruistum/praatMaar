@echo off
cd /d "%~dp0"

REM Voorkeur: gebouwde exe (toont "praatMaar" in Windows-pictogrammenlijst).
if exist "dist\praatMaar\praatMaar.exe" (
  "dist\praatMaar\praatMaar.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\praatMaar\praatMaar.exe" (
  "%LOCALAPPDATA%\praatMaar\praatMaar.exe"
  goto :eof
)

if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\pythonw.exe" dictation.py
) else (
  pythonw dictation.py
)
