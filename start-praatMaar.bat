@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\pythonw.exe" dictation.py
) else (
  pythonw dictation.py
)
