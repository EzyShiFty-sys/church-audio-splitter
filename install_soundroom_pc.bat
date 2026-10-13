@echo off
setlocal enabledelayedexpansion
title Church Audio Splitter - Soundroom PC Installer
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo       HOUSE OF REFUGE - CHURCH AUDIO SPLITTER INSTALLER
echo                       Soundroom PC Edition
echo ==============================================================================
echo.

:: 1. Check Python installation
echo [*] Checking for Python...
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python was not found in PATH!
    echo [*] Attempting to install Python 3.11 via winget...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Please install Python 3.10 or newer from python.org
        echo Make sure to check the box: Add Python to PATH!
        pause
        exit /b 1
    ) else (
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        echo [*] Python installed. Please RESTART this installer so PATH updates.
        pause
        exit /b 0
    )
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Detected %PY_VER%

:: 2. Check FFmpeg installation
echo [*] Checking for FFmpeg...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [!] FFmpeg not found in standard PATH.
    echo [*] Trying winget install Gyan.FFmpeg...
    where winget >nul 2>nul
    if not errorlevel 1 (
        winget install Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
        echo [OK] FFmpeg installed via winget.
    ) else (
        echo [!] Warning: FFmpeg not detected via winget.
    )
) else (
    echo [OK] FFmpeg found!
)

:: 3. Setup Python Virtual Environment
echo.
echo [*] Setting up local Python Virtual Environment (venv)...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python venv is available.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found.
)

:: 4. Upgrade pip and install dependencies
echo.
echo [*] Installing dependencies: FastAPI, Faster-Whisper, PyTorch/CTranslate2...
echo [*] This takes 1-3 minutes depending on your internet connection...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [!] requirements.txt install reported an issue, trying pip install . ...
    venv\Scripts\python.exe -m pip install .
)

:: 5. Create Desktop Shortcut via PowerShell
echo.
echo [*] Creating Desktop Shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Church Audio Splitter.lnk')); $s.TargetPath = '%~dp0START_CHURCH_SPLITTER.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Launch Church Audio Splitter Dashboard'; $s.Save()"
echo [OK] Desktop shortcut "Church Audio Splitter" created!

echo.
echo ==============================================================================
echo [SUCCESS] Church Audio Splitter is ready to use on your Soundroom PC!
echo ==============================================================================
echo.
echo You can launch it anytime using:
echo   1. The Desktop shortcut: "Church Audio Splitter"
echo   2. Double-clicking: START_CHURCH_SPLITTER.bat
echo.
echo Press any key to launch Church Audio Splitter now...
pause >nul

start "" "%~dp0START_CHURCH_SPLITTER.bat"
