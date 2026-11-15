@echo off
setlocal
if defined CODECUT_PYTHON (
  "%CODECUT_PYTHON%" "%~dp0editor.py" %*
) else if exist "C:\Users\cheng\AppData\Local\Programs\Python\Python312\python.exe" (
  "C:\Users\cheng\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0editor.py" %*
) else (
  python "%~dp0editor.py" %*
)
exit /b %errorlevel%
