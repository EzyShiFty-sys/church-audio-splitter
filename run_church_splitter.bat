@echo off
setlocal
cd /d "%~dp0"

set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin;%PATH%"

echo ===================================================
echo     Church Service Audio Splitter (Whisper + FFmpeg)
echo ===================================================
echo.
echo Launching Web UI at http://127.0.0.1:8000 ...
echo Press Ctrl+C in this terminal to stop the server.
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m church_splitter.cli ui --port 8000
) else (
    uv run python -m church_splitter.cli ui --port 8000
)

pause
