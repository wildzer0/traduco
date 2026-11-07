@echo off
rem Traduco launcher bootstrap (Windows 10/11). Double-click to start. No admin rights needed.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
rem Windows PowerShell 5.1 breaks when it inherits the module path of PowerShell 7 (e.g. started from pwsh).
set "PSModulePath=%WINDIR%\System32\WindowsPowerShell\v1.0\Modules"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\bootstrap.ps1" %*
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" (
  echo.
  echo Traduco stopped with an error. See .runtime\logs for details.
  pause
)
exit /b %CODE%
