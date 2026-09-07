@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -u dispatch_local.py >> local_dispatch.log 2>&1
exit /b %errorlevel%
