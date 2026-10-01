import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

DEFAULT_MODEL_SIZE = "base"  # "tiny", "base", "small", "medium"
DEFAULT_WINDOW_SECONDS = 180  # 3-minute sliding window for density calculation
DEFAULT_MIN_SERMON_MINUTES = 10.0  # Minimum sermon length in minutes
DEFAULT_SPEECH_DENSITY_THRESHOLD = 0.55  # Minimum ratio of active speech in window to qualify as sermon
DEFAULT_GAP_TOLERANCE_SECONDS = 45.0  # Allow gaps (scripture reading pauses, laughter, prayer) up to 45s
DEFAULT_PADDING_SECONDS = 2.0  # Cushion buffer in seconds around cuts

def find_ffmpeg() -> str:
    """Finds ffmpeg binary in PATH or common Windows winget installation paths."""
    # Check standard PATH
    path = shutil.which("ffmpeg")
    if path:
        return path
    
    # Check Windows WinGet standard install locations
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for ffmpeg_match in winget_pkgs.glob("**/ffmpeg.exe"):
                if ffmpeg_match.is_file():
                    return str(ffmpeg_match)
                    
    # Check Program Files
    for prog_dir in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
        if prog_dir:
            for ffmpeg_match in Path(prog_dir).glob("**/ffmpeg.exe"):
                if ffmpeg_match.is_file():
                    return str(ffmpeg_match)
                    
    return "ffmpeg"

def find_ffprobe() -> str:
    """Finds ffprobe binary in PATH or common Windows winget installation paths."""
    path = shutil.which("ffprobe")
    if path:
        return path
        
    ffmpeg_bin = find_ffmpeg()
    if ffmpeg_bin and ffmpeg_bin != "ffmpeg":
        probe_sibling = Path(ffmpeg_bin).parent / "ffprobe.exe"
        if probe_sibling.is_file():
            return str(probe_sibling)
            
    return "ffprobe"
