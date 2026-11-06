@echo off
title Vattara AI Voice Assistant - Backend Server (:8000)
color 0A
echo ========================================================
echo  Starting Vattara AI Voice Assistant Backend (Port 8000)
echo ========================================================
echo.
cd /d "%~dp0backend"
call ".\venv\Scripts\activate.bat"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
