@echo off
rem Start CodeGame on its own (it also opens inside Lumen with @CodeGame).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codegame" "%PYW%" "%~dp0..\tools\codegame\editor.py"
