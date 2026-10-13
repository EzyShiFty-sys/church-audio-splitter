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
if %ERRORLEVEL% neq 0 (
    echo [!] Python was not found in PATH!
    echo [*] Attempting to install Python 3.11 via Windows Package Manager (winget)...
    where winget >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        echo [*] Python installed. Please RESTART this installer so PATH updates.
        pause
        exit /b 0
    ) else (
        echo [ERROR] Please install Python 3.10+ from https://www.python.org/downloads/
        echo Make sure to CHECK THE BOX: "Add Python to PATH" during installation!
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Detected %PY_VER%

:: 2. Check FFmpeg installation
echo [*] Checking for FFmpeg...
where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] FFmpeg not found in standard PATH.
    echo [*] Trying winget install Gyan.FFmpeg...
    where winget >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        winget install Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
        echo [OK] FFmpeg installed via winget.
    ) else (
        echo [!] Warning: FFmpeg not detected. If splits fail, install FFmpeg or place ffmpeg.exe in this folder.
    )
) else (
    echo [OK] FFmpeg found!
)

:: 3. Setup Python Virtual Environment
echo.
echo [*] Setting up local Python Virtual Environment (venv)...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
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
echo [*] Installing dependencies (FastAPI, Faster-Whisper, PyTorch/CTranslate2)...
echo [*] This takes 1-2 minutes depending on your internet connection...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [!] Retrying with pyproject...
    venv\Scripts\python.exe -m pip install .
)

:: 5. Create Desktop Shortcut
echo.
echo [*] Creating Desktop Shortcut...
set "SHORTCUT_SCRIPT=%TEMP%\create_cas_shortcut.vbs"
set "TARGET_BAT=%~dp0START_CHURCH_SPLITTER.bat"
(
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
    echo sLinkFile = oWS.SpecialFolders^("Desktop"^) ^& "\Church Audio Splitter.lnk"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^)
    echo oLink.TargetPath = "%TARGET_BAT%"
    echo oLink.WorkingDirectory = "%~dp0"
    echo oLink.Description = "Launch Church Audio Splitter Dashboard"
    echo oLink.Save
) > "%SHORTCUT_SCRIPT%"
cscript //nologo "%SHORTCUT_SCRIPT%" >nul 2>nul
del "%SHORTCUT_SCRIPT%" 2>nul
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
