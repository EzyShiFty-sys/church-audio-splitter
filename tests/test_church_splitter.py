import os
import sys
import numpy as np
import soundfile as sf
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from church_splitter.splitter import ChurchAudioSplitter
from church_splitter.ffmpeg_utils import get_audio_info, lossless_cut

def generate_synthetic_church_audio(filepath: Path, duration_sec: int = 180):
    """
    Generates a synthetic church service audio:
    - 0 to 45s: Worship music (harmonic chords / pads)
    - 45s to 140s: Sermon (modulated speech-like pulses with pauses)
    - 140s to 180s: Closing worship (harmonic chords)
    """
    sample_rate = 44100
    t = np.linspace(0, duration_sec, duration_sec * sample_rate, endpoint=False)
    audio = np.zeros_like(t)

    # 1. Opening Worship (0 - 45s): Chords (C major: 261.63Hz, 329.63Hz, 392.00Hz)
    worship1_mask = (t >= 0) & (t < 45)
    audio[worship1_mask] = 0.3 * (
        np.sin(2 * np.pi * 261.63 * t[worship1_mask]) +
        np.sin(2 * np.pi * 329.63 * t[worship1_mask]) +
        np.sin(2 * np.pi * 392.00 * t[worship1_mask])
    )

    # 2. Sermon (45s - 140s): Speech-like formant bursts & modulated frequencies with regular pauses
    sermon_mask = (t >= 45) & (t < 140)
    speech_carrier = (
        np.sin(2 * np.pi * 150 * t[sermon_mask]) +
        0.5 * np.sin(2 * np.pi * 500 * t[sermon_mask]) +
        0.3 * np.sin(2 * np.pi * 1500 * t[sermon_mask])
    )
    # Modulate with speech syllable cadence (~4Hz) and sentence pauses (~every 8s)
    cadence = (np.sin(2 * np.pi * 3.5 * t[sermon_mask]) > 0).astype(float)
    sentence_pause = (np.sin(2 * np.pi * 0.15 * t[sermon_mask]) > -0.7).astype(float)
    audio[sermon_mask] = 0.4 * speech_carrier * cadence * sentence_pause

    # 3. Closing Worship (140s - 180s): F major chord (349.23Hz, 440.00Hz, 523.25Hz)
    worship2_mask = (t >= 140) & (t <= 180)
    audio[worship2_mask] = 0.3 * (
        np.sin(2 * np.pi * 349.23 * t[worship2_mask]) +
        np.sin(2 * np.pi * 440.00 * t[worship2_mask]) +
        np.sin(2 * np.pi * 523.25 * t[worship2_mask])
    )

    # Normalize
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.8
    filepath.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(filepath), audio.astype(np.float32), sample_rate)
    print(f"Generated test audio at: {filepath} ({duration_sec}s)")

def test_workflow():
    test_dir = Path(__file__).resolve().parent / "test_output"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_audio = test_dir / "sample_church_service.wav"

    generate_synthetic_church_audio(test_audio, duration_sec=120)

    # Verify ffprobe info
    info = get_audio_info(test_audio)
    print(f"Probe info: {info['duration']}s, codec: {info['codec']}, sample_rate: {info['sample_rate']}")
    assert info["duration"] > 100

    # Test lossless cutting directly
    cut1 = test_dir / "test_worship.wav"
    lossless_cut(test_audio, cut1, start_sec=0.0, end_sec=30.0)
    info_cut1 = get_audio_info(cut1)
    print(f"Lossless cut 1 duration: {info_cut1['duration']}s")
    assert abs(info_cut1["duration"] - 30.0) < 1.0

    print("[OK] Unit test for lossless cutting passed successfully!")

if __name__ == "__main__":
    test_workflow()
