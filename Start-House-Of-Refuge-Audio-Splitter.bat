@echo off
title House of Refuge Audio Splitter
echo ========================================================
echo   House of Refuge Church - Audio Splitter & Spotify Tool
echo   https://houseofrefugechurch.net/
echo ========================================================
echo.
cd /d "c:\Users\nedmo_u3wbbic\Dev Projects\church-audio-splitter"

echo Starting Church Audio Splitter...
echo Opening browser at http://127.0.0.1:8000 ...

:: Launch default browser after 1 second delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: Start Uvicorn Server via uv
uv run python -m church_splitter.cli ui --port 8000

pause
