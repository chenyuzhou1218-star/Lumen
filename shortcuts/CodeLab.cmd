@echo off
rem Start CodeLab on its own (it also opens inside Lumen with @CodeLab).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codelab" "%PYW%" "%~dp0..\tools\codelab\editor.py"
