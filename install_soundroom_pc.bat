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

:: 1. Check for real Python installation (ignoring Microsoft Store dummy stubs)
echo [*] Checking for Python...
set "PY_CMD="

:: Check common Python installation paths directly
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python311\python.exe"
) else if exist "%ProgramFiles%\Python312\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python312\python.exe"
) else (
    :: Test if python in PATH is functional
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
    echo [!] Python 3.10+ was not found on this system.
    echo [*] Downloading official Python 3.11 64-bit installer from python.org...
    
    :: Try curl first (built into Windows, fast and handles Fastly/CDN redirects)
    where curl >nul 2>nul
    if not errorlevel 1 (
        curl.exe -fSL -o "%TEMP%\python_setup.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    )
    
    :: Fallback to PowerShell
    if not exist "%TEMP%\python_setup.exe" (
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $wc = New-Object System.Net.WebClient; $wc.Headers.Add('User-Agent','Mozilla/5.0'); $wc.DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '$env:TEMP\python_setup.exe')"
    )
    
    :: If download failed, open browser directly to the download file
    if not exist "%TEMP%\python_setup.exe" (
        echo.
        echo [!] Automatic background download was blocked by Windows security.
        echo [*] Opening the official Python 3.11 download in your browser...
        start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        echo.
        echo --------------------------------------------------------------------------
        echo ACTION REQUIRED:
        echo 1. Your browser will download: python-3.11.9-amd64.exe
        echo 2. Run the downloaded file.
        echo 3. VERY IMPORTANT: Check the box 'Add Python to PATH' at the bottom!
        echo 4. Click 'Install Now' and wait for it to finish.
        echo --------------------------------------------------------------------------
        echo Once Python installation is finished, press any key to continue...
        pause >nul
    ) else (
        echo [*] Installing Python 3.11 (this takes ~30 seconds)...
        start /wait "" "%TEMP%\python_setup.exe" /passive InstallAllUsers=0 PrependPath=1 Include_pip=1
        del "%TEMP%\python_setup.exe" 2>nul
    )
    
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) else if exist "%ProgramFiles%\Python311\python.exe" (
        set "PY_CMD=%ProgramFiles%\Python311\python.exe"
    ) else (
        echo [OK] Python installed! Please close and re-run install_soundroom_pc.bat to continue.
        pause
        exit /b 0
    )
)

for /f "tokens=*" %%v in ('"%PY_CMD%" --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Using %PY_VER% (%PY_CMD%)

:: 2. Check for FFmpeg installation (PATH or local bin folder)
echo.
echo [*] Checking for FFmpeg...
set "HAS_FFMPEG=0"
if exist "%~dp0bin\ffmpeg.exe" (
    set "HAS_FFMPEG=1"
) else (
    where ffmpeg >nul 2>nul
    if not errorlevel 1 set "HAS_FFMPEG=1"
)

if "%HAS_FFMPEG%"=="0" (
    echo [!] FFmpeg not found. Downloading portable FFmpeg binaries into bin/...
    if not exist "%~dp0bin" mkdir "%~dp0bin"
    
    where curl >nul 2>nul
    if not errorlevel 1 (
        curl.exe -fSL -o "%TEMP%\ffmpeg.zip" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    )
    if not exist "%TEMP%\ffmpeg.zip" (
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', '$env:TEMP\ffmpeg.zip')"
    )
    if exist "%TEMP%\ffmpeg.zip" (
        powershell -NoProfile -Command "Expand-Archive -Path '$env:TEMP\ffmpeg.zip' -DestinationPath '$env:TEMP\ffmpeg_extracted' -Force; Get-ChildItem -Path '$env:TEMP\ffmpeg_extracted' -Recurse -Filter 'ffmpeg.exe' | ForEach-Object { Copy-Item $_.FullName -Destination '%~dp0bin\ffmpeg.exe' }; Get-ChildItem -Path '$env:TEMP\ffmpeg_extracted' -Recurse -Filter 'ffprobe.exe' | ForEach-Object { Copy-Item $_.FullName -Destination '%~dp0bin\ffprobe.exe' }; Remove-Item '$env:TEMP\ffmpeg.zip' -Force -ErrorAction SilentlyContinue; Remove-Item '$env:TEMP\ffmpeg_extracted' -Recurse -Force -ErrorAction SilentlyContinue"
    )
    if exist "%~dp0bin\ffmpeg.exe" (
        echo [OK] Portable FFmpeg downloaded and installed into bin/!
    ) else (
        echo [!] Warning: Automatic FFmpeg download could not complete. Audio splitting may require FFmpeg in PATH.
    )
) else (
    echo [OK] FFmpeg found!
)

:: 3. Setup Python Virtual Environment
echo.
echo [*] Setting up local Python Virtual Environment (venv)...
if not exist "%~dp0venv\Scripts\python.exe" (
    "%PY_CMD%" -m venv "%~dp0venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv. Make sure Python has venv enabled.
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
"%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [!] Retrying package installation with pip install -e . ...
    "%~dp0venv\Scripts\python.exe" -m pip install -e "%~dp0"
)

:: 5. Create Desktop Shortcut via PowerShell
echo.
echo [*] Creating Desktop Shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Church Audio Splitter.lnk')); $s.TargetPath = '%~dp0START_CHURCH_SPLITTER.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Launch Church Audio Splitter Dashboard'; $s.Save()"
echo [OK] Desktop shortcut "Church Audio Splitter" created on your Desktop!

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
