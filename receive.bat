@echo off
cd /d "%~dp0"

echo Checking Dire Wolf...
tasklist | find /i "direwolf.exe" >nul
if errorlevel 1 (
    echo Starting Dire Wolf in background...
    start /min "" direwolf.exe
    echo Waiting for Dire Wolf to initialize...
    timeout /t 3 /nobreak >nul
) else (
    echo Dire Wolf already running.
)

echo Starting RX...
py rx.py -s

pause
