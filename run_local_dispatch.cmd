@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON_EXE=C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe"
cd /d "%~dp0"
if not exist "%PYTHON_EXE%" (
  echo HOLD: configured Python executable is missing>> local_dispatch.log
  exit /b 2
)
"%PYTHON_EXE%" -u dispatch_local.py %* >> local_dispatch.log 2>&1
exit /b %errorlevel%
