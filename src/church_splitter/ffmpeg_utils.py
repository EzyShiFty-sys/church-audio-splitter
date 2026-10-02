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
    end_sec: Optional[float] = None,
    metadata: Optional[Dict[str, str]] = None,
    cover_art_path: Optional[str | Path] = None,
    normalize_loudness: bool = False
) -> None:
    """
    Performs audio cutting with optional ID3/RIFF metadata tagging,
    album cover art embedding, and EBU R128 (-16 LUFS) broadcast loudness normalization.
    Uses FFmpeg stream copy (-c copy) whenever possible for lossless zero-degradation output.
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg()
    
    is_mp3_output = output_path.suffix.lower() == ".mp3"
    input_is_wav = input_path.suffix.lower() == ".wav"
    has_cover_art = bool(cover_art_path and Path(cover_art_path).exists() and is_mp3_output)
    reencode_needed = normalize_loudness or (is_mp3_output and input_is_wav)

    cmd = [ffmpeg_bin, "-y"]
    
    # Input seek
    if start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
        
    cmd.extend(["-i", str(input_path)])
    
    if end_sec is not None:
        duration_to_cut = end_sec - (start_sec if start_sec > 0 else 0)
        if duration_to_cut > 0:
            cmd.extend(["-t", f"{duration_to_cut:.3f}"])

    if has_cover_art:
        cmd.extend(["-i", str(Path(cover_art_path).resolve())])
        cmd.extend(["-map", "0:a", "-map", "1:0"])

    # Loudness normalization or audio encoding
    if normalize_loudness:
        cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
        if is_mp3_output:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k"])
        else:
            cmd.extend(["-c:a", "pcm_s16le"])
    elif reencode_needed:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k"])
    else:
        cmd.extend(["-c:a", "copy"] if has_cover_art else ["-c", "copy"])

    # Embed cover art video stream for MP3 ID3v2
    if has_cover_art:
        cmd.extend([
            "-c:v", "mjpeg",
            "-id3v2_version", "3",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)"
        ])

    # Metadata tagging (Title, Artist, Album, Year, Genre, Track)
    if metadata:
        for k, v in metadata.items():
            if v is not None and str(v).strip():
                cmd.extend(["-metadata", f"{k}={str(v).strip()}"])

    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg cut failed: {result.stderr}")

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

def detect_silence_pauses(
    audio_path: str | Path,
    start_sec: float = 0.0,
    duration_sec: Optional[float] = None,
    noise_db: float = -28.0,
    min_silence_duration: float = 2.0
) -> List[Dict[str, float]]:
    """Detects pause/silence intervals using FFmpeg silencedetect."""
    import re
    ffmpeg_bin = find_ffmpeg()
    cmd = [ffmpeg_bin]
    if start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.2f}"])
    if duration_sec:
        cmd.extend(["-t", f"{duration_sec:.2f}"])
    cmd.extend([
        "-i", str(Path(audio_path).resolve()),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_duration}",
        "-f", "null",
        "-"
    ])
    result = subprocess.run(cmd, capture_output=True, text=True)
    pauses = []
    current_start = None
    for line in result.stderr.splitlines():
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([\d\.]+)", line)
            if m:
                current_start = float(m.group(1)) + start_sec
        elif "silence_end:" in line and current_start is not None:
            m = re.search(r"silence_end:\s*([\d\.]+)\s*\|\s*silence_duration:\s*([\d\.]+)", line)
            if m:
                end_t = float(m.group(1)) + start_sec
                dur = float(m.group(2))
                pauses.append({"start": current_start, "end": end_t, "duration": dur})
            current_start = None
    return pauses
