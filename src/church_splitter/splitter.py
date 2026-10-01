import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from church_splitter.speech_analyzer import ChurchAudioAnalyzer, SermonDetectionResult
from church_splitter.ffmpeg_utils import lossless_cut, lossless_concat, get_audio_info

def format_timestamp(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    seconds = max(0.0, float(seconds))
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

class ChurchAudioSplitter:
    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.analyzer = ChurchAudioAnalyzer(model_size=model_size, device=device)

    def analyze_service(
        self,
        audio_path: str | Path,
        window_seconds: float = 180.0,
        min_sermon_minutes: float = 10.0,
        density_threshold: float = 0.55,
        gap_tolerance: float = 45.0,
        padding_seconds: float = 2.0,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> SermonDetectionResult:
        """Runs Whisper speech density analysis on the audio file."""
        return self.analyzer.analyze(
            audio_path=audio_path,
            window_seconds=window_seconds,
            min_sermon_minutes=min_sermon_minutes,
            density_threshold=density_threshold,
            gap_tolerance=gap_tolerance,
            padding_seconds=padding_seconds,
            progress_callback=progress_callback
        )

    def export_splits(
        self,
        input_audio_path: str | Path,
        output_dir: str | Path,
        sermon_start: float,
        sermon_end: float,
        combine_worship: bool = False,
        export_transcript: bool = True,
        sermon_transcript: str = "",
        custom_base_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Takes the detected/adjusted start and end timestamps and uses FFmpeg lossless cutting
        (-c copy) to produce high-fidelity separate files for Worship Music and Sermon.
        """
        input_audio_path = Path(input_audio_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        info = get_audio_info(input_audio_path)
        total_duration = info["duration"]
        ext = input_audio_path.suffix.lower()
        base_name = custom_base_name or input_audio_path.stem

        created_files: List[Dict[str, Any]] = []

        # 1. Worship Part 1 (Pre-Sermon)
        worship_parts_to_concat = []
        if sermon_start > 1.0:
            worship1_filename = f"{base_name}_01_Worship_Opening{ext}"
            worship1_path = output_dir / worship1_filename
            lossless_cut(
                input_path=input_audio_path,
                output_path=worship1_path,
                start_sec=0.0,
                end_sec=sermon_start
            )
            created_files.append({
                "type": "worship_part1",
                "label": "Worship (Opening)",
                "filename": worship1_filename,
                "path": str(worship1_path),
                "start": 0.0,
                "end": sermon_start,
                "duration": sermon_start,
                "formatted_range": f"{format_timestamp(0)} - {format_timestamp(sermon_start)}"
            })
            worship_parts_to_concat.append(worship1_path)

        # 2. Sermon
        sermon_filename = f"{base_name}_02_Sermon{ext}"
        sermon_path = output_dir / sermon_filename
        lossless_cut(
            input_path=input_audio_path,
            output_path=sermon_path,
            start_sec=sermon_start,
            end_sec=sermon_end
        )
        created_files.append({
            "type": "sermon",
            "label": "Sermon",
            "filename": sermon_filename,
            "path": str(sermon_path),
            "start": sermon_start,
            "end": sermon_end,
            "duration": sermon_end - sermon_start,
            "formatted_range": f"{format_timestamp(sermon_start)} - {format_timestamp(sermon_end)}"
        })

        # 3. Worship Part 2 (Post-Sermon / Closing)
        if sermon_end < (total_duration - 1.0):
            worship2_filename = f"{base_name}_03_Worship_Closing{ext}"
            worship2_path = output_dir / worship2_filename
            lossless_cut(
                input_path=input_audio_path,
                output_path=worship2_path,
                start_sec=sermon_end,
                end_sec=total_duration
            )
            created_files.append({
                "type": "worship_part2",
                "label": "Worship (Closing & Response)",
                "filename": worship2_filename,
                "path": str(worship2_path),
                "start": sermon_end,
                "end": total_duration,
                "duration": total_duration - sermon_end,
                "formatted_range": f"{format_timestamp(sermon_end)} - {format_timestamp(total_duration)}"
            })
            worship_parts_to_concat.append(worship2_path)

        # 4. Combined Worship (if requested and multiple parts exist)
        if combine_worship and len(worship_parts_to_concat) > 1:
            combined_filename = f"{base_name}_Full_Worship_Combined{ext}"
            combined_path = output_dir / combined_filename
            lossless_concat(worship_parts_to_concat, combined_path)
            created_files.append({
                "type": "worship_combined",
                "label": "Full Worship (Combined)",
                "filename": combined_filename,
                "path": str(combined_path),
                "duration": sum(p.stat().st_size for p in worship_parts_to_concat) # approx
            })

        # 5. Export Sermon Transcript if available
        if export_transcript and sermon_transcript:
            transcript_filename = f"{base_name}_Sermon_Transcript.txt"
            transcript_path = output_dir / transcript_filename
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(f"--- SERMON TRANSCRIPT ---\n")
                f.write(f"Audio Source: {input_audio_path.name}\n")
                f.write(f"Timestamps: {format_timestamp(sermon_start)} - {format_timestamp(sermon_end)}\n\n")
                f.write(sermon_transcript)
                f.write("\n")
            created_files.append({
                "type": "transcript",
                "label": "Sermon Transcript",
                "filename": transcript_filename,
                "path": str(transcript_path)
            })

        # 6. Save split summary metadata json
        summary_filename = f"{base_name}_split_summary.json"
        summary_path = output_dir / summary_filename
        summary_data = {
            "source_file": str(input_audio_path),
            "source_duration_seconds": total_duration,
            "sermon_start_seconds": sermon_start,
            "sermon_end_seconds": sermon_end,
            "sermon_formatted_range": f"{format_timestamp(sermon_start)} - {format_timestamp(sermon_end)}",
            "files": created_files
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        return summary_data
