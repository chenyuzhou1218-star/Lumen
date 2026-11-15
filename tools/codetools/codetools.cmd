@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codetools.py" %*
) else (
  python "%~dp0codetools.py" %*
)
exit /b %errorlevel%
