@echo off
cd /d "%~dp0\.."
start "F1 Snapshot Server" .venv\Scripts\python.exe -m flask --app src.app run
timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:5000
