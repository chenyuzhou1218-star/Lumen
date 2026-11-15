@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codelab.py" %*
) else (
  python "%~dp0codelab.py" %*
)
exit /b %errorlevel%
