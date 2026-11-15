@echo off
rem Start CodeFilm on its own (it also opens inside Lumen with @CodeFilm).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codefilm" "%PYW%" "%~dp0..\tools\codefilm\editor.py"
