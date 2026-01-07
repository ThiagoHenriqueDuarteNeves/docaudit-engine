@echo off
echo.
echo ===================================================
echo 🚀 Start DocAudit Engine
echo ===================================================
echo.

:: 1. Navigate to Project Root (ABSOLUTE PATH so it works from Desktop)
cd /d "c:\Users\Thiago\Documents\005 - DocAudit Engine"

:: 2. Start Backend (New Window)
echo [1/2] Launching Backend...
start "DocAudit Backend" cmd /k "run_backend_debug.bat"

:: 3. Start Frontend (New Window)
echo [2/2] Launching Frontend...
cd frontend
start "DocAudit Frontend" cmd /k "npm run dev"

echo.
echo ✅ Systems starting in background windows...
echo Closing this launcher in 5 seconds...
timeout /t 5
exit
