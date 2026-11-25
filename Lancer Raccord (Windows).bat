@echo off
rem Lance Raccord avec une console (utile pour voir les messages en cas de souci).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Lancez d abord "Installer Raccord (Windows).bat".
  pause
  exit /b 1
)
set "PATH=%~dp0outils\ffmpeg\bin;%PATH%"
".venv\Scripts\python.exe" -X utf8 app\fenetre.py
if errorlevel 1 pause
