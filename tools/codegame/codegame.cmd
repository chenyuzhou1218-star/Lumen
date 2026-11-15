@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codegame.py" %*
) else (
  python "%~dp0codegame.py" %*
)
exit /b %errorlevel%
