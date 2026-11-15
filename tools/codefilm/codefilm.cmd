@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codefilm.py" %*
) else (
  python "%~dp0codefilm.py" %*
)
exit /b %errorlevel%
