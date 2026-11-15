@echo off
rem Start Lumen. Run setup.ps1 once first.
if not exist "%~dp0.venv\Scripts\pythonw.exe" (echo Run setup.ps1 first. & pause & exit /b 1)
start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" -m codedoctor.desktop.app
