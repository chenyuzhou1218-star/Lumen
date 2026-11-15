@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codesound.py" %*
) else (
  python "%~dp0codesound.py" %*
)
exit /b %errorlevel%
