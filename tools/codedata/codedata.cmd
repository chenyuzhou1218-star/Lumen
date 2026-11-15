@echo off
setlocal
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codedata.py" %*
) else (
  python "%~dp0codedata.py" %*
)
exit /b %errorlevel%
