# PowerShell launcher for Church Audio Splitter
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$env:PATH = "$env:USERPROFILE\.local\bin;$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin;$env:PATH"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    Church Service Audio Splitter (Whisper + FFmpeg)" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Launching Web UI at http://127.0.0.1:8000 ..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C in this terminal to stop the server." -ForegroundColor Gray
Write-Host ""

if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    & "$ScriptDir\.venv\Scripts\python.exe" -m church_splitter.cli ui --port 8000
} else {
    uv run python -m church_splitter.cli ui --port 8000
}
