@echo off
setlocal
if defined CODECUT_PYTHON (
  "%CODECUT_PYTHON%" "%~dp0codecut.py" %*
) else if exist "C:\Users\cheng\AppData\Local\Programs\Python\Python312\python.exe" (
  "C:\Users\cheng\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0codecut.py" %*
) else (
  python "%~dp0codecut.py" %*
)
exit /b %errorlevel%
