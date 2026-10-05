import sys
import os
import shutil
import zipfile
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("=== Building House of Refuge Audio Splitter Portable Bundle ===")

project_root = Path(__file__).resolve().parent.parent
build_dir = project_root / "dist" / "House-Of-Refuge-Audio-Splitter-Portable"
zip_output = project_root / "dist" / "House-Of-Refuge-Audio-Splitter-Portable.zip"

if build_dir.exists():
    shutil.rmtree(build_dir)
build_dir.mkdir(parents=True, exist_ok=True)

# 1. Copy bin (ffmpeg & ffprobe)
print("1. Copying FFmpeg binaries...")
bin_dir = build_dir / "bin"
bin_dir.mkdir(exist_ok=True)
src_ffmpeg_dir = Path(r"C:\Users\nedmo_u3wbbic\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin")
shutil.copy2(src_ffmpeg_dir / "ffmpeg.exe", bin_dir / "ffmpeg.exe")
shutil.copy2(src_ffmpeg_dir / "ffprobe.exe", bin_dir / "ffprobe.exe")
print("   ✓ ffmpeg.exe & ffprobe.exe copied")

# 2. Copy Standalone Python
print("2. Copying standalone Python 3.11 x86_64...")
src_python = Path(r"C:\Users\nedmo_u3wbbic\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none")
dst_python = build_dir / "python"
# Copy necessary python files (skip tcl to save ~40MB)
def ignore_py(d, names):
    if Path(d).name == "tcl":
        return names
    return [n for n in names if n.endswith(".pdb") or n == "__pycache__"]

shutil.copytree(src_python, dst_python, ignore=ignore_py)
print("   ✓ Standalone Python copied")

# 3. Copy site-packages
print("3. Copying installed packages (fastapi, faster-whisper, torch, etc.)...")
src_sp = project_root / ".venv" / "Lib" / "site-packages"
dst_sp = build_dir / "site-packages"

def ignore_sp(d, names):
    return [n for n in names if n.endswith(".dist-info") and "record" in n.lower() or n == "__pycache__"]

shutil.copytree(src_sp, dst_sp, ignore=ignore_sp)
print("   ✓ Site-packages copied")

# 4. Copy pre-downloaded Whisper models
print("4. Copying Whisper speech models...")
src_models = Path(r"C:\Users\nedmo_u3wbbic\.cache\huggingface")
dst_models = build_dir / "models" / "huggingface"
if src_models.exists():
    shutil.copytree(src_models, dst_models)
    print("   ✓ Whisper models copied (base & tiny)")
else:
    print("   ⚠️ Models directory not found, skipping pre-bundled weights")

# 5. Copy App Code & Web Assets
print("5. Copying application code and static UI...")
shutil.copytree(project_root / "src", build_dir / "src")
shutil.copytree(project_root / "static", build_dir / "static")
shutil.copy2(project_root / "pyproject.toml", build_dir / "pyproject.toml")
print("   ✓ Code and Web UI assets copied")

# 6. Create Start-House-Of-Refuge-Audio-Splitter.bat
print("6. Creating Start-House-Of-Refuge-Audio-Splitter.bat...")
bat_content = """@echo off
setlocal
title House of Refuge Audio Splitter
echo =====================================================================
echo          House of Refuge Church - Audio Splitter & Spotify Tool
echo                     https://houseofrefugechurch.net/
echo =====================================================================
echo.

cd /d "%~dp0"

:: Set paths to bundled portable Python, FFmpeg, and packages
set "PATH=%~dp0bin;%~dp0python;%PATH%"
set "PYTHONPATH=%~dp0src;%~dp0site-packages"
set "HF_HOME=%~dp0models\\huggingface"

echo [1/3] Using bundled FFmpeg and portable speech engine...
echo [2/3] Starting Church Audio Splitter web server on port 8000...
echo [3/3] Opening browser at http://127.0.0.1:8000 ...
echo.
echo Press CTRL+C at any time in this window to stop the server.
echo.

:: Automatically open default web browser after 2 seconds
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: Run the FastAPI Web UI server
"%~dp0python\\python.exe" -m church_splitter.cli ui --port 8000

if %ERRORLEVEL% neq 0 (
    echo.
    echo =====================================================================
    echo The server stopped or encountered an unexpected issue.
    echo =====================================================================
    pause
)
"""
with open(build_dir / "Start-House-Of-Refuge-Audio-Splitter.bat", "w", encoding="utf-8") as f:
    f.write(bat_content)

# 7. Create Create-Desktop-Shortcut.bat
print("7. Creating Create-Desktop-Shortcut.bat...")
shortcut_bat = """@echo off
title Create Desktop Shortcut
echo Creating desktop shortcut for House of Refuge Audio Splitter...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut($desk + '\\House of Refuge Audio Splitter.lnk'); $s.TargetPath = '%~dp0Start-House-Of-Refuge-Audio-Splitter.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%SystemRoot%\\System32\\shell32.dll,280'; $s.Description = 'House of Refuge Church Audio Splitter'; $s.Save()"
echo.
echo [DONE] Shortcut created on your Desktop! You can now launch the app directly from your Desktop.
echo.
pause
"""
with open(build_dir / "Create-Desktop-Shortcut.bat", "w", encoding="utf-8") as f:
    f.write(shortcut_bat)

# 8. Create README.txt
print("8. Creating README.txt...")
readme_content = """================================================================================
     HOUSE OF REFUGE CHURCH - PORTABLE AUDIO SPLITTER & SPOTIFY TOOL
                     Website: https://houseofrefugechurch.net/
================================================================================

This is a 100% self-contained, portable Windows application.
It requires NO installation, NO Python setup, NO administrative rights,
and works completely OFFLINE without requiring church internet!

--------------------------------------------------------------------------------
HOW TO SET UP ON THE CHURCH COMPUTER (ONE TIME SETUP):
--------------------------------------------------------------------------------
1. Copy this entire "House-Of-Refuge-Audio-Splitter-Portable" folder onto the
   church computer. 
   Recommended location:
     C:\\HouseOfRefugeAudioSplitter
   (You can also run it directly from your UGREEN NAS or a USB drive!)

2. Inside the folder, double-click:
     "Create-Desktop-Shortcut.bat"
   This will place a "House of Refuge Audio Splitter" shortcut icon directly
   on the church computer's desktop!

--------------------------------------------------------------------------------
SERVICE WORKFLOW & NEW FEATURES:
--------------------------------------------------------------------------------
1. RECORD IN AUDACITY:
   - Record the church service in Audacity as usual.
   - When finished, export/save the full recording into your UGREEN NAS folder
     (e.g., Z:\Audacity_Recordings or \\UGREEN-NAS\ChurchAudio).

2. LAUNCH THE SPLITTER:
   - Double-click "House of Refuge Audio Splitter" on your Desktop.
   - Your web browser will open automatically to http://127.0.0.1:8000.

3. SET SERVICE TYPE & MESSAGE TITLE:
   - Service / Event Dropdown:
     * Sunday Morning Service (12:00 PM)
     * Sunday School - Adult Teaching (11:00 AM)
     * Wednesday Evening Service
     * Friday Evening Service
     * Revival / Special Meeting
   - Message / Sermon Title:
     * Type the sermon title (e.g., "One Look Is All It Took", "Walking in Faith").
     * The title is automatically embedded into the MP3 tags, output filename,
       and the Spotify episode notes!

4. MULTI-TRACK SERVICE SPLITTING & WORSHIP SONGS:
   - Separate every worship song sung, Sunday School teaching, preaching, and altar calls:
     * Click a Quick Preset:
       - "☀️ Sunday School + Service": Sets up Adult Teaching at 11 AM and Service at 12 PM
       - "📖 Sunday Morning": Breaks opening praise into individual songs + Preaching + Altar
       - "🕯️ Wednesday Night" / "🔥 Friday Night": Tailored for midweek prayer & teaching
       - "🪄 Revival Meeting": Handles high-energy multi-part revival services
       - "🎵 Auto-Detect Song Breaks": Automatically finds natural pauses between worship songs!
   - Select Exactly Which Tracks to Export:
     * Check or uncheck individual tracks with the [x] checkboxes.
     * Use quick buttons: "All", "📖 Preaching Only", "🎵 Worship Songs Only", or "None".
     * Click "✂️ Export Selected Tracks" to export only the tracks you want.
     * Need just one specific track or song? Click "✂️ Export This" on any row!
     * Ready for Spotify? Click "📖 Export Preaching Only (Direct for Spotify)" to get just the sermon with 1 click!

5. PUBLISH TO SPOTIFY FOR CREATORS & CHURCH WEBSITE:
   - Open Spotify for Creators in your browser.
   - Drag in the finished Preaching MP3 file.
   - In the Splitter app, click "📋 Copy for Spotify" to copy formatted scripture references,
     key quotes, and service show notes (properly labeled with Sunday School, Wednesday, Friday, etc.).
   - Paste directly into the Spotify episode description!
   - Grab the Spotify episode share link and add it to https://houseofrefugechurch.net/.

--------------------------------------------------------------------------------
TECHNICAL DETAILS:
--------------------------------------------------------------------------------
- Audio Engine: FFmpeg 9.0.2 Lossless Stream Demuxer (-c copy)
- Speech Density VAD: OpenAI Whisper Base Speech Recognition (Offline Weights)
- Broadcast Standard: EBU R128 (-16 LUFS integrated loudness, -1.5 dB true peak)
- ID3 Standard: ID3v2.3 with APIC attached picture album art
- Requirements: Windows 10 or 11 (64-bit)

Created with care for House of Refuge Church!
================================================================================
"""
with open(build_dir / "README.txt", "w", encoding="utf-8") as f:
    f.write(readme_content)

# 9. Create Zip Archive
print("9. Creating standalone ZIP archive: dist/House-Of-Refuge-Audio-Splitter-Portable.zip ...")
with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
    for root, dirs, files in os.walk(build_dir):
        for file in files:
            file_path = Path(root) / file
            arcname = file_path.relative_to(build_dir.parent)
            zipf.write(file_path, arcname)

zip_size_mb = zip_output.stat().st_size / (1024 * 1024)
print(f"   ✓ ZIP archive created successfully: {zip_size_mb:.1f} MB")
print("\n=== BUILD COMPLETE ===")
