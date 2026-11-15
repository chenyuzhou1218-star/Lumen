@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
  "%~dp0..\..\.venv\Scripts\python.exe" "%~dp0codepdf.py" %*
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0codepdf.py" %*
) else (
  python "%~dp0codepdf.py" %*
)
exit /b %errorlevel%
