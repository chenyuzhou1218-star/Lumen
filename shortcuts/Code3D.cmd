@echo off
rem Start Code3D on its own (it also opens inside Lumen with @Code3D).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
rem Lumen's own .venv, when setup.ps1 put the tools' libraries there
if exist "%~dp0..\.venv\Lib\site-packages\playwright" set "PYW=%~dp0..\.venv\Scripts\pythonw.exe"
start "" /D "%~dp0..\tools\code3d" "%PYW%" "%~dp0..\tools\code3d\editor.py"
