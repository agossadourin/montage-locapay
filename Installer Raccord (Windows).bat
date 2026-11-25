@echo off
rem Installation de Raccord (a lancer une seule fois). Comptez 10 a 20 minutes.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\installer.ps1"
