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

            def get_transcribe_iterator():
                nonlocal model
                try:
                    seg_iter, _ = model.transcribe(
                        tmp_wav_path,
                        beam_size=1,
                        word_timestamps=False,
                        vad_filter=True,
                        vad_parameters=dict(
                            min_silence_duration_ms=500,
                            speech_pad_ms=200
                        )
                    )
                    first_item = next(seg_iter, None)
                    return seg_iter, first_item
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
                        seg_iter, _ = model.transcribe(
                            tmp_wav_path,
                            beam_size=1,
                            word_timestamps=False,
                            vad_filter=True,
                            vad_parameters=dict(
                                min_silence_duration_ms=500,
                                speech_pad_ms=200
                            )
                        )
                        first_item = next(seg_iter, None)
                        return seg_iter, first_item
                    raise e

            seg_iter, first_item = get_transcribe_iterator()
            import itertools
            raw_stream = itertools.chain([first_item] if first_item is not None else [], seg_iter)

            speech_segments: List[SpeechSegment] = []
            all_text_parts: List[str] = []

            for seg in raw_stream:
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
                    mins_done = int(seg.end // 60)
                    mins_total = int(total_duration // 60)
                    pct_done = int((seg.end / total_duration) * 100)
                    progress_callback(current_pct, f"Transcribing speech: {mins_done}m / {mins_total}m ({pct_done}% of audio)...")

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
        Uses cadence-weighted sliding window active-speech density and contiguous
        sustained region detection to separate singing worship music from spoken preaching.
        """
        duration_int = int(np.ceil(total_duration))
        if duration_int <= 0:
            return [], 0.0, 0.0, 0.0

        speech_mask = np.zeros(duration_int, dtype=np.float32)
        words_per_sec = np.zeros(duration_int, dtype=np.float32)

        for seg in speech_segments:
            s_idx = max(0, int(np.floor(seg.start)))
            e_idx = min(duration_int, int(np.ceil(seg.end)))
            dur = seg.end - seg.start
            words = seg.words_count
            if dur > 0 and words > 0 and e_idx > s_idx:
                wps = words / dur
                # Speaking rate: 1.5 - 4.0 words/sec; worship singing: < 0.6 words/sec
                # Realistic speaking time: max ~0.45s per word
                speech_time = min(dur, words * 0.45)
                activity_ratio = min(1.0, speech_time / dur)
                cadence_factor = float(np.clip((wps - 0.4) / 1.0, 0.05, 1.0))
                seg_intensity = activity_ratio * cadence_factor

                speech_mask[s_idx:e_idx] = np.maximum(speech_mask[s_idx:e_idx], seg_intensity)
                words_per_sec[s_idx:e_idx] = np.maximum(words_per_sec[s_idx:e_idx], wps)

        # Sliding window rolling density (180s default)
        win_size = max(10, int(window_seconds))
        kernel = np.ones(win_size) / win_size
        raw_density = np.convolve(speech_mask, kernel, mode="same")
        # Normalize: continuous speech (~0.45 raw intensity) maps cleanly to ~1.0, worship singing to ~0.0-0.1
        density_profile = np.clip(raw_density / 0.45, 0.0, 1.0)

        # Downsample density timeline for UI visualization
        timeline_density: List[Dict[str, float]] = []
        step = 5
        for t in range(0, duration_int, step):
            timeline_density.append({
                "time": float(t),
                "density": float(round(density_profile[t], 3)),
                "words_per_sec": float(round(words_per_sec[t], 2))
            })

        # Find candidate blocks where density meets sensitivity threshold
        effective_thresh = max(0.20, density_threshold * 0.7)
        active_mask = (density_profile >= effective_thresh).astype(int)

        # Bridge pauses within preaching up to gap_tolerance seconds
        gap_limit = max(15, int(gap_tolerance))
        last_active = -1
        bridged_speech_mask = active_mask.copy()
        for i in range(duration_int):
            if active_mask[i] == 1:
                if last_active != -1 and (i - last_active) <= gap_limit:
                    bridged_speech_mask[last_active:i] = 1
                last_active = i

        # Extract contiguous candidate regions
        changes = np.diff(bridged_speech_mask)
        starts = np.where(changes == 1)[0] + 1
        ends = np.where(changes == -1)[0] + 1
        if bridged_speech_mask[0] == 1:
            starts = np.insert(starts, 0, 0)
        if bridged_speech_mask[-1] == 1:
            ends = np.append(ends, duration_int)

        min_sermon_secs = min_sermon_minutes * 60.0
        valid_candidates = []
        for cs, ce in zip(starts, ends):
            dur = ce - cs
            if dur >= min_sermon_secs:
                avg_density = float(np.mean(density_profile[cs:ce]))
                valid_candidates.append((cs, ce, dur, avg_density))

        # If no single candidate meets the full minimum, pick the longest sustained block
        if not valid_candidates and len(starts) > 0:
            all_cands = [(s, e, e - s, float(np.mean(density_profile[s:e]))) for s, e in zip(starts, ends)]
            sorted_cands = sorted(all_cands, key=lambda c: c[2], reverse=True)
            valid_candidates.append(sorted_cands[0])

        if not valid_candidates:
            # Fallback: center 50%
            fallback_start = total_duration * 0.25
            fallback_end = total_duration * 0.75
            return timeline_density, fallback_start, fallback_end, 0.30

        # Choose the candidate with highest sustained preaching score
        best_candidate = max(valid_candidates, key=lambda x: x[2] * (x[3] ** 1.5))
        raw_start, raw_end, cand_dur, cand_density = best_candidate

        # Refine boundaries against actual speech segments near raw_start and raw_end
        matched_segs = [s for s in speech_segments if s.end >= (raw_start - 30) and s.start <= (raw_end + 30) and s.words_count >= 3]
        if matched_segs:
            refined_start = max(0.0, matched_segs[0].start - padding_seconds)
            refined_end = min(total_duration, matched_segs[-1].end + padding_seconds)
        else:
            refined_start = max(0.0, float(raw_start) - padding_seconds)
            refined_end = min(total_duration, float(raw_end) + padding_seconds)

        confidence = min(1.0, float(cand_density * (min(1.0, cand_dur / max(min_sermon_secs, 1.0)))))
        return timeline_density, refined_start, refined_end, confidence
