@echo off
rem Traduco launcher bootstrap (Windows 10/11). Double-click to start. No admin rights needed.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\bootstrap.ps1" %*
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" (
  echo.
  echo Traduco stopped with an error. See .runtime\logs for details.
  pause
)
exit /b %CODE%
