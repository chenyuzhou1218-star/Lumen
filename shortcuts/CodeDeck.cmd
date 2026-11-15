@echo off
rem Start CodeDeck on its own (it also opens inside Lumen with @CodeDeck).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codedeck" "%PYW%" "%~dp0..\tools\codedeck\editor.py"
