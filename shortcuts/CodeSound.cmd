@echo off
rem Start CodeSound on its own (it also opens inside Lumen with @CodeSound).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codesound" "%PYW%" "%~dp0..\tools\codesound\editor.py"
