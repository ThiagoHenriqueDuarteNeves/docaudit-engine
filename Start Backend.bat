@echo off
echo.
echo ===================================================
echo 🚀 Start DocAudit BACKEND ONLY
echo ===================================================
echo.

:: 1. Navigate to Project Root
cd /d "%~dp0"

:: 2. Execute Backend Script
call "scripts\run_backend_debug.bat"

pause
