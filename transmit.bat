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

if "%~1"=="" (
    echo Drag an image file onto this BAT file
    pause
    exit /b
)

set /p CALLSIGN=Enter callsign: 

if "%CALLSIGN%"=="" (
    echo Callsign cannot be empty.
    pause
    exit /b
)

py tx.py %CALLSIGN% "%~1"

pause
