@echo off
title Vattara AI Voice Assistant - Frontend Vite (:5173)
color 0B
echo ========================================================
echo  Starting Vattara AI Voice Assistant Frontend (Port 5173)
echo ========================================================
echo.
cd /d "%~dp0frontend"
call npm run dev
pause
