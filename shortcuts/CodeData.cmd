@echo off
rem Start CodeData on its own (it also opens inside Lumen with @CodeData).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codedata" "%PYW%" "%~dp0..\tools\codedata\editor.py"
