@echo off
rem Start CodePage on its own (it also opens inside Lumen with @CodePage).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codepage" "%PYW%" "%~dp0..\tools\codepage\editor.py"
