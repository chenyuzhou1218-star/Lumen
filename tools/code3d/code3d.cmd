@echo off
setlocal
if defined CODE3D_PYTHON (
  "%CODE3D_PYTHON%" "%~dp0code3d.py" %*
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0code3d.py" %*
) else (
  python "%~dp0code3d.py" %*
)
exit /b %errorlevel%
