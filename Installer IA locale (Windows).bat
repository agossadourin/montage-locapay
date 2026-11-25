@echo off
rem Installe l IA locale gratuite (Ollama) et l active dans Raccord.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\ollama.ps1"
