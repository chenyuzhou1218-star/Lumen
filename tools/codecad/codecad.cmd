@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codecad.py" %*
) else (
  python "%~dp0codecad.py" %*
)
exit /b %errorlevel%
