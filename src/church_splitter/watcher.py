import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from church_splitter.splitter import ChurchAudioSplitter
from church_splitter.scripture_extractor import generate_social_summary

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac"}

class ChurchAudioWatcher:
    """
    Watches a designated folder for new church service audio recordings.
    Automatically verifies copy completion, runs speech density detection,
    extracts scripture references, and exports tagged/normalized audio splits.
    """
    def __init__(
        self,
        watch_folder: str | Path,
        output_folder: Optional[str | Path] = None,
        default_preacher: str = "",
        default_series: str = "",
        default_genre: str = "Sermon",
        cover_art_path: Optional[str | Path] = None,
        normalize_loudness: bool = False,
        export_mp3: bool = False,
        model_size: str = "base",
        poll_interval: float = 4.0
    ):
        self.watch_folder = Path(watch_folder).resolve()
        self.output_folder = Path(output_folder).resolve() if output_folder else (self.watch_folder / "Auto_Splits")
        self.default_preacher = default_preacher
        self.default_series = default_series
        self.default_genre = default_genre
        self.cover_art_path = str(Path(cover_art_path).resolve()) if cover_art_path else None
        self.normalize_loudness = normalize_loudness
        self.export_mp3 = export_mp3
        self.model_size = model_size
        self.poll_interval = poll_interval

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.status = "stopped"  # stopped, watching, processing, error
        self.current_file: Optional[str] = None
        self.logs: List[str] = []
        self.history_file = self.output_folder / ".processed_recordings.json"

    def log(self, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        entry = f"[{now}] {message}"
        self.logs.append(entry)
        if len(self.logs) > 200:
            self.logs.pop(0)
        print(f"[Watcher] {entry}")

    def _load_history(self) -> set:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.get("processed_files", []))
            except Exception:
                return set()
        return set()

    def _save_history(self, processed_set: set):
        self.output_folder.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"processed_files": list(processed_set)}, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save processed history: {e}")

    def start(self):
        if self._running:
            return
        self._running = True
        self.status = "watching"
        self.watch_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.log(f"Watcher started on: {self.watch_folder}")
        self.log(f"Output directory: {self.output_folder}")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self.status = "stopped"
        self.log("Watcher stopped.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "status": self.status,
            "watch_folder": str(self.watch_folder),
            "output_folder": str(self.output_folder),
            "current_file": self.current_file,
            "default_preacher": self.default_preacher,
            "default_series": self.default_series,
            "normalize_loudness": self.normalize_loudness,
            "export_mp3": self.export_mp3,
            "has_cover_art": bool(self.cover_art_path and Path(self.cover_art_path).exists()),
            "logs": self.logs[-50:]
        }

    def _is_file_stable(self, file_path: Path) -> bool:
        """Checks if a file has finished copying/recording by checking size stability."""
        try:
            s1 = file_path.stat().st_size
            if s1 == 0:
                return False
            time.sleep(3.0)
            s2 = file_path.stat().st_size
            if s1 != s2:
                return False
            # Test exclusive read
            with open(file_path, "rb") as f:
                f.read(1024)
            return True
        except (PermissionError, OSError):
            return False

    def _run_loop(self):
        processed = self._load_history()
        while self._running:
            try:
                for entry in self.watch_folder.iterdir():
                    if not self._running:
                        break
                    if not entry.is_file() or entry.suffix.lower() not in SUPPORTED_EXTENSIONS:
                        continue
                    if entry.name.startswith(".") or entry.name in processed:
                        continue

                    self.log(f"Detected new recording candidate: {entry.name}")
                    self.status = "waiting_for_stability"
                    self.current_file = entry.name

                    # Ensure copy is completed
                    if not self._is_file_stable(entry):
                        self.log(f"File {entry.name} is still being written or copied. Waiting...")
                        continue

                    # Process file
                    self.status = "processing"
                    self.log(f"🚀 Auto-processing service recording: {entry.name}...")
                    self._process_recording(entry)
                    processed.add(entry.name)
                    self._save_history(processed)
                    self.log(f"✅ Successfully processed & split: {entry.name}")

                self.status = "watching"
                self.current_file = None
            except Exception as e:
                self.log(f"Error in watcher loop: {e}")
                self.status = "error"

            time.sleep(self.poll_interval)

    def _process_recording(self, file_path: Path):
        splitter = ChurchAudioSplitter(model_size=self.model_size)
        
        # 1. Analyze
        self.log(f"Analyzing speech density on {file_path.name}...")
        res = splitter.analyze_service(file_path)

        # 2. Extract Scripture & Title
        extracted = generate_social_summary(
            res.sermon_transcript,
            preacher=self.default_preacher,
            series=self.default_series
        )
        sermon_title = extracted.get("title") or "Sunday Message"
        self.log(f"Detected Title: '{sermon_title}', Scripture: {', '.join(extracted.get('scriptures', []))}")

        # 3. Export splits
        target_dir = self.output_folder / file_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "artist": self.default_preacher or "Church Service",
            "album": self.default_series or "Sermon Archive",
            "year": str(datetime.now().year),
            "genre": self.default_genre,
            "title": sermon_title
        }

        self.log(f"Exporting splits with metadata to {target_dir}...")
        summary = splitter.export_splits(
            input_audio_path=file_path,
            output_dir=target_dir,
            sermon_start=res.sermon_start,
            sermon_end=res.sermon_end,
            combine_worship=True,
            export_transcript=True,
            sermon_transcript=res.sermon_transcript,
            metadata=meta,
            cover_art_path=self.cover_art_path,
            normalize_loudness=self.normalize_loudness,
            export_mp3=self.export_mp3
        )

        # 4. Save Social Media post info alongside splits
        post_path = target_dir / f"{file_path.stem}_Social_Media_Post.txt"
        with open(post_path, "w", encoding="utf-8") as f:
            f.write(extracted.get("social_post", ""))
        self.log(f"Created ready-to-share social post: {post_path.name}")
