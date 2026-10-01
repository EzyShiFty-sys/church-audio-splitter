import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from church_splitter.config import find_ffmpeg, find_ffprobe

def get_audio_info(audio_path: str | Path) -> Dict[str, Any]:
    """Uses ffprobe to extract duration, format, bitrate, sample rate, and audio streams."""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    ffprobe_bin = find_ffprobe()
    cmd = [
        ffprobe_bin,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(audio_path.resolve())
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(result.stdout)

    format_data = probe_data.get("format", {})
    duration = float(format_data.get("duration", 0.0))
    bit_rate = int(format_data.get("bit_rate", 0)) if format_data.get("bit_rate") else None
    
    # Get audio stream specifics
    streams = probe_data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    codec = audio_streams[0].get("codec_name", "unknown") if audio_streams else "unknown"
    sample_rate = int(audio_streams[0].get("sample_rate", 44100)) if audio_streams else 44100
    channels = int(audio_streams[0].get("channels", 2)) if audio_streams else 2

    return {
        "path": str(audio_path.resolve()),
        "filename": audio_path.name,
        "extension": audio_path.suffix.lower(),
        "duration": duration,
        "bit_rate": bit_rate,
        "codec": codec,
        "sample_rate": sample_rate,
        "channels": channels,
        "size_bytes": audio_path.stat().st_size
    }

def extract_resampled_wav(audio_path: str | Path, output_wav_path: str | Path) -> None:
    """Downsamples audio to 16kHz mono 16-bit PCM WAV for Whisper speech analysis."""
    ffmpeg_bin = find_ffmpeg()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(Path(audio_path).resolve()),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(Path(output_wav_path).resolve())
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def lossless_cut(
    input_path: str | Path,
    output_path: str | Path,
    start_sec: float,
    end_sec: Optional[float] = None
) -> None:
    """
    Performs lossless audio cutting using FFmpeg stream copy (-c copy).
    Preserves exact audio stream data, bitrate, and quality without re-encoding.
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg()
    
    # Using input seeking with -ss before -i and -to for fast lossless cutting
    cmd = [ffmpeg_bin, "-y"]
    
    # Precise seek
    if start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
        
    cmd.extend(["-i", str(input_path)])
    
    if end_sec is not None:
        duration_to_cut = end_sec - (start_sec if start_sec > 0 else 0)
        if duration_to_cut > 0:
            cmd.extend(["-t", f"{duration_to_cut:.3f}"])

    cmd.extend(["-c", "copy", str(output_path)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg lossless cut failed: {result.stderr}")

def lossless_concat(input_paths: List[str | Path], output_path: str | Path) -> None:
    """Concatenates multiple audio files of identical codec/format losslessly using concat demuxer."""
    if not input_paths:
        return
    if len(input_paths) == 1:
        shutil.copyfile(input_paths[0], output_path)
        return

    ffmpeg_bin = find_ffmpeg()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        temp_list_path = f.name
        for p in input_paths:
            # Escape path for ffmpeg concat demuxer
            safe_p = str(Path(p).resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_p}'\n")

    try:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_list_path,
            "-c", "copy",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")
    finally:
        if os.path.exists(temp_list_path):
            os.remove(temp_list_path)
