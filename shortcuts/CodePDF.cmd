@echo off
rem Start CodePDF on its own (it also opens inside Lumen with @CodePDF).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\codepdf" "%PYW%" "%~dp0..\tools\codepdf\editor.py"
