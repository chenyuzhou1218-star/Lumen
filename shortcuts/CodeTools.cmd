@echo off
rem Start CodeTools on its own (it also opens inside Lumen with @CodeTools).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codetools" "%PYW%" "%~dp0..\tools\codetools\editor.py"
