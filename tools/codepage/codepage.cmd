@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codepage.py" %*
) else (
  python "%~dp0codepage.py" %*
)
exit /b %errorlevel%
