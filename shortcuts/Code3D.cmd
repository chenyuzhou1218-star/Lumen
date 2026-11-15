@echo off
rem Start Code3D on its own (it also opens inside Lumen with @Code3D).
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /D "%~dp0..\tools\code3d" "%PYW%" "%~dp0..\tools\code3d\editor.py"
