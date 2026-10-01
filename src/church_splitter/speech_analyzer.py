import os
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
import numpy as np
from faster_whisper import WhisperModel
from church_splitter.ffmpeg_utils import extract_resampled_wav, get_audio_info
from church_splitter.config import (
    DEFAULT_MODEL_SIZE,
    DEFAULT_WINDOW_SECONDS,
    DEFAULT_MIN_SERMON_MINUTES,
    DEFAULT_SPEECH_DENSITY_THRESHOLD,
    DEFAULT_GAP_TOLERANCE_SECONDS,
    DEFAULT_PADDING_SECONDS
)

@dataclass
class SpeechSegment:
    start: float
    end: float
    text: str
    words_count: int
    avg_logprob: float
    no_speech_prob: float

@dataclass
class SermonDetectionResult:
    sermon_start: float
    sermon_end: float
    sermon_duration: float
    total_duration: float
    confidence: float
    worship_segments: List[Dict[str, float]]
    timeline_density: List[Dict[str, float]]
    segments: List[Dict[str, Any]]
    transcript_text: str
    sermon_transcript: str

class ChurchAudioAnalyzer:
    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "auto",
        compute_type: str = "default"
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[WhisperModel] = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            # Try CUDA if requested or auto, with seamless fallback to CPU int8
            if self.device in ("cuda", "auto"):
                try:
                    self._model = WhisperModel(
                        self.model_size,
                        device="cuda",
                        compute_type="float16",
                        cpu_threads=os.cpu_count() or 4
                    )
                    return self._model
                except Exception:
                    pass

            # Safe CPU initialization with optimized int8 quantization
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=os.cpu_count() or 4
            )
        return self._model

    def analyze(
        self,
        audio_path: str | Path,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        min_sermon_minutes: float = DEFAULT_MIN_SERMON_MINUTES,
        density_threshold: float = DEFAULT_SPEECH_DENSITY_THRESHOLD,
        gap_tolerance: float = DEFAULT_GAP_TOLERANCE_SECONDS,
        padding_seconds: float = DEFAULT_PADDING_SECONDS,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SermonDetectionResult:
        """
        Transcribes audio with Whisper, calculates sliding-window speech density,
        and identifies the sermon start and end timestamps.
        """
        audio_path = Path(audio_path).resolve()
        info = get_audio_info(audio_path)
        total_duration = info["duration"]

        if total_duration <= 0:
            raise ValueError(f"Invalid audio file duration: {total_duration}")

        if progress_callback:
            progress_callback(0.05, "Extracting audio for speech analysis...")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name

        try:
            extract_resampled_wav(audio_path, tmp_wav_path)
            
            if progress_callback:
                progress_callback(0.15, f"Loading Whisper model ({self.model_size})...")
            
            model = self._get_model()

            if progress_callback:
                progress_callback(0.20, "Transcribing and detecting speech timestamps...")

            try:
                segments_raw, info_whisper = model.transcribe(
                    tmp_wav_path,
                    beam_size=3,
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=200
                    )
                )
                # Force evaluation of first item to catch lazy CUDA loading errors
                segments_list = []
                for seg in segments_raw:
                    segments_list.append(seg)
            except Exception as e:
                # If CUDA runtime failed (e.g. missing cublas64_12.dll), recreate on CPU
                if "cublas" in str(e).lower() or "cuda" in str(e).lower():
                    self._model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=os.cpu_count() or 4
                    )
                    model = self._model
                    segments_raw, info_whisper = model.transcribe(
                        tmp_wav_path,
                        beam_size=3,
                        word_timestamps=True,
                        vad_filter=True,
                        vad_parameters=dict(
                            min_silence_duration_ms=500,
                            speech_pad_ms=200
                        )
                    )
                    segments_list = list(segments_raw)
                else:
                    raise e

            speech_segments: List[SpeechSegment] = []
            all_text_parts: List[str] = []

            for seg in segments_list:
                cleaned_text = seg.text.strip()
                words = cleaned_text.split()
                speech_segments.append(
                    SpeechSegment(
                        start=round(seg.start, 2),
                        end=round(seg.end, 2),
                        text=cleaned_text,
                        words_count=len(words),
                        avg_logprob=round(seg.avg_logprob, 3),
                        no_speech_prob=round(seg.no_speech_prob, 3)
                    )
                )
                if cleaned_text:
                    all_text_parts.append(f"[{seg.start:.1f}s - {seg.end:.1f}s] {cleaned_text}")

                if progress_callback and total_duration > 0:
                    current_pct = 0.20 + min(0.65, (seg.end / total_duration) * 0.65)
                    progress_callback(current_pct, f"Analyzing speech: {int(seg.end//60)}m / {int(total_duration//60)}m...")

        finally:
            if os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except Exception:
                    pass

        if progress_callback:
            progress_callback(0.85, "Calculating speech density profile...")

        # Build 1-second resolution speech activity array
        timeline_density, sermon_start, sermon_end, confidence = self._detect_sermon_bounds(
            speech_segments=speech_segments,
            total_duration=total_duration,
            window_seconds=window_seconds,
            min_sermon_minutes=min_sermon_minutes,
            density_threshold=density_threshold,
            gap_tolerance=gap_tolerance,
            padding_seconds=padding_seconds
        )

        # Determine worship segments based on sermon boundaries
        worship_segments = []
        if sermon_start > 2.0:
            worship_segments.append({
                "name": "Worship_Part1_Opening",
                "start": 0.0,
                "end": sermon_start
            })
        if sermon_end < total_duration - 2.0:
            worship_segments.append({
                "name": "Worship_Part2_Closing",
                "start": sermon_end,
                "end": total_duration
            })

        # Extract sermon transcript
        sermon_words: List[str] = []
        for s in speech_segments:
            if s.start >= (sermon_start - 2.0) and s.end <= (sermon_end + 2.0):
                sermon_words.append(s.text)
        sermon_transcript = " ".join(sermon_words).strip()

        if progress_callback:
            progress_callback(1.0, "Analysis complete!")

        return SermonDetectionResult(
            sermon_start=round(sermon_start, 2),
            sermon_end=round(sermon_end, 2),
            sermon_duration=round(sermon_end - sermon_start, 2),
            total_duration=round(total_duration, 2),
            confidence=round(confidence, 3),
            worship_segments=worship_segments,
            timeline_density=timeline_density,
            segments=[asdict(s) for s in speech_segments],
            transcript_text="\n".join(all_text_parts),
            sermon_transcript=sermon_transcript
        )

    def _detect_sermon_bounds(
        self,
        speech_segments: List[SpeechSegment],
        total_duration: float,
        window_seconds: float,
        min_sermon_minutes: float,
        density_threshold: float,
        gap_tolerance: float,
        padding_seconds: float
    ) -> Tuple[List[Dict[str, float]], float, float, float]:
        """
        Uses sliding window active-speech density and contiguous sustained region detection.
        """
        duration_int = int(np.ceil(total_duration))
        if duration_int <= 0:
            return [], 0.0, 0.0, 0.0

        speech_mask = np.zeros(duration_int, dtype=np.float32)
        words_per_sec = np.zeros(duration_int, dtype=np.float32)

        for seg in speech_segments:
            s_idx = max(0, int(np.floor(seg.start)))
            e_idx = min(duration_int, int(np.ceil(seg.end)))
            if e_idx > s_idx:
                speech_mask[s_idx:e_idx] = 1.0
                seg_dur = seg.end - seg.start
                if seg_dur > 0:
                    words_per_sec[s_idx:e_idx] += (seg.words_count / seg_dur)

        # Sliding window rolling density
        win_size = max(10, int(window_seconds))
        # Use uniform 1D convolution
        kernel = np.ones(win_size) / win_size
        density_profile = np.convolve(speech_mask, kernel, mode="same")

        # Downsample density timeline for visualization (e.g. 5-second steps)
        timeline_density: List[Dict[str, float]] = []
        step = 5
        for t in range(0, duration_int, step):
            timeline_density.append({
                "time": float(t),
                "density": float(round(density_profile[t], 3)),
                "words_per_sec": float(round(words_per_sec[t], 2))
            })

        # Find high-density contiguous blocks
        # 1. Active speech regions bridged by gap_tolerance
        bridged_speech_mask = speech_mask.copy()
        gap_limit = int(gap_tolerance)
        last_speech = -1
        for i in range(duration_int):
            if speech_mask[i] > 0:
                if last_speech != -1 and (i - last_speech) <= gap_limit:
                    bridged_speech_mask[last_speech:i] = 1.0
                last_speech = i

        # 2. Extract contiguous candidate regions
        candidates = []
        in_region = False
        r_start = 0

        for i in range(duration_int):
            # Check if this point is in high speech density or bridged speech
            is_active = (density_profile[i] >= density_threshold) or (bridged_speech_mask[i] > 0 and density_profile[i] >= (density_threshold * 0.7))
            if is_active and not in_region:
                in_region = True
                r_start = i
            elif not is_active and in_region:
                in_region = False
                r_end = i
                candidates.append((r_start, r_end))
        if in_region:
            candidates.append((r_start, duration_int))

        # Filter candidates by minimum sermon duration
        min_sermon_secs = min_sermon_minutes * 60.0
        valid_candidates = []
        for cs, ce in candidates:
            dur = ce - cs
            if dur >= min_sermon_secs:
                avg_density = np.mean(density_profile[cs:ce])
                valid_candidates.append((cs, ce, dur, avg_density))

        # If no single candidate meets the full minimum, pick the longest sustained block
        if not valid_candidates and candidates:
            # Sort by duration
            sorted_cands = sorted(candidates, key=lambda c: (c[1] - c[0]), reverse=True)
            best_c = sorted_cands[0]
            valid_candidates.append((best_c[0], best_c[1], best_c[1] - best_c[0], float(np.mean(density_profile[best_c[0]:best_c[1]]))))

        if not valid_candidates:
            # Fallback: take the center 50% of the service if nothing detected
            fallback_start = total_duration * 0.25
            fallback_end = total_duration * 0.75
            return timeline_density, fallback_start, fallback_end, 0.30

        # Choose the candidate with highest score (combining duration and speech density)
        # Score = duration * (avg_density ** 1.5)
        best_candidate = max(valid_candidates, key=lambda x: x[2] * (x[3] ** 1.5))
        raw_start, raw_end, cand_dur, cand_density = best_candidate

        # Refine start and end by matching actual speech segments near raw_start and raw_end
        # Find first speech segment >= raw_start - 30s
        matched_segs = [s for s in speech_segments if s.end >= (raw_start - 30) and s.start <= (raw_end + 30)]
        if matched_segs:
            refined_start = max(0.0, matched_segs[0].start - padding_seconds)
            refined_end = min(total_duration, matched_segs[-1].end + padding_seconds)
        else:
            refined_start = max(0.0, float(raw_start) - padding_seconds)
            refined_end = min(total_duration, float(raw_end) + padding_seconds)

        confidence = min(1.0, float(cand_density * (min(1.0, cand_dur / max(min_sermon_secs, 1.0)))))
        return timeline_density, refined_start, refined_end, confidence
