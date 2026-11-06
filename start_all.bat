@echo off
title Launch Vattara Voice Assistance Suite
echo ========================================================
echo  Launching Vattara AI Voice Assistance Full-Stack App
echo ========================================================
echo.
echo 1. Launching Backend on http://127.0.0.1:8000...
start "Vattara Backend (:8000)" cmd /k "cd /d %~dp0backend && call .\venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo 2. Launching Frontend on http://localhost:5173...
start "Vattara Frontend (:5173)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================================
echo  Both servers started successfully!
echo  Visit your app at: http://localhost:5173
echo ========================================================
timeout /t 5 >nul
