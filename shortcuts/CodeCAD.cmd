@echo off
rem Start CodeCAD on its own (it also opens inside Lumen with @CodeCAD).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codecad" "%PYW%" "%~dp0..\tools\codecad\editor.py"
