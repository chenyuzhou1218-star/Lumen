@echo off
rem Start CodeCut on its own (it also opens inside Lumen with @CodeCut).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codecut" "%PYW%" "%~dp0..\tools\codecut\editor.py"
