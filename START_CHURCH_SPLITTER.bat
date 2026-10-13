@echo off
setlocal enabledelayedexpansion
title Church Audio Splitter Dashboard
color 0a
cd /d "%~dp0"

echo ==============================================================================
echo     HOUSE OF REFUGE - CHURCH AUDIO SPLITTER & SERMON DETECTOR
echo ==============================================================================
echo.

:: Check if environment exists
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not detected.
    echo [*] Running first-time setup installer...
    call "%~dp0install_soundroom_pc.bat"
    exit /b 0
)

:: Add potential FFmpeg paths to session PATH
for /d %%d in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
    for /d %%b in ("%%d\ffmpeg-*\bin") do (
        set "PATH=%%b;!PATH!"
    )
)

echo [*] Starting Web Server on http://localhost:8000 ...
echo [*] Accessible locally at: http://localhost:8000
echo [*] Close this window anytime to stop the application.
echo.

:: Automatically open default browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Run FastAPI server with PYTHONPATH set to src
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
venv\Scripts\python.exe -m church_splitter.server --port 8000 --host 0.0.0.0

pause
