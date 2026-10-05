import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from church_splitter.splitter import ChurchAudioSplitter, format_timestamp
from church_splitter.ffmpeg_utils import get_audio_info, find_ffmpeg, lossless_cut
from church_splitter.scripture_extractor import generate_social_summary, extract_scriptures, extract_sermon_title
from church_splitter.watcher import ChurchAudioWatcher

app = FastAPI(title="Church Audio Splitter API")

# Global active jobs store and watcher
analysis_jobs: Dict[str, Dict[str, Any]] = {}
active_watcher: Optional[ChurchAudioWatcher] = None
current_cover_art_path: Optional[str] = None

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class AnalyzeRequest(BaseModel):
    audio_path: str
    model_size: str = "base"
    min_sermon_minutes: float = 10.0
    density_threshold: float = 0.55
    gap_tolerance: float = 45.0
    padding_seconds: float = 2.0

class TrackItem(BaseModel):
    label: str
    start: float
    end: float
    track_number: Optional[int] = None

class MultiTrackExportRequest(BaseModel):
    audio_path: str
    output_dir: str
    tracks: List[TrackItem]
    custom_base_name: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    cover_art_path: Optional[str] = None
    normalize_loudness: bool = False
    export_mp3: bool = False

class DetectSongsRequest(BaseModel):
    audio_path: str
    worship_end: float = 3954.0

class ResplitTrackRequest(BaseModel):
    source_audio_path: str
    output_path: str
    start: float
    end: float
    metadata: Optional[Dict[str, str]] = None
    cover_art_path: Optional[str] = None
    normalize_loudness: bool = False

class LoadSummaryRequest(BaseModel):
    folder_path: str

class ExportRequest(BaseModel):
    audio_path: str
    output_dir: str
    sermon_start: float
    sermon_end: float
    combine_worship: bool = False
    export_transcript: bool = True
    sermon_transcript: Optional[str] = ""
    custom_base_name: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    cover_art_path: Optional[str] = None
    normalize_loudness: bool = False
    export_mp3: bool = False

class ExtractSermonInfoRequest(BaseModel):
    transcript: str
    title: Optional[str] = None
    preacher: Optional[str] = None
    series: Optional[str] = None
    service_type: Optional[str] = None

class WatcherStartRequest(BaseModel):
    watch_folder: str
    output_folder: Optional[str] = None
    default_preacher: Optional[str] = ""
    default_series: Optional[str] = ""
    default_genre: Optional[str] = "Sermon"
    normalize_loudness: bool = False
    export_mp3: bool = False
    cover_art_path: Optional[str] = None
    model_size: str = "base"

@app.get("/api/system-info")
async def get_system_info():
    return {
        "ffmpeg_path": find_ffmpeg(),
        "status": "ready"
    }

@app.post("/api/file-info")
async def probe_file(audio_path: str):
    p = Path(audio_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    try:
        info = get_audio_info(p)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/upload")
async def upload_audio_file(file: UploadFile = File(...)):
    upload_dir = Path(os.environ.get("TEMP", "/tmp")) / "church_audio_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / file.filename

    with open(target_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    info = get_audio_info(target_path)
    return {
        "path": str(target_path),
        "info": info
    }

@app.post("/api/analyze")
async def analyze_audio(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    p = Path(req.audio_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    job_id = str(abs(hash(req.audio_path + str(req.model_size) + str(os.path.getmtime(p)))))
    analysis_jobs[job_id] = {
        "status": "running",
        "progress": 0.05,
        "message": "Starting analysis...",
        "result": None,
        "error": None
    }

    def run_analysis():
        try:
            splitter = ChurchAudioSplitter(model_size=req.model_size)
            
            def cb(pct, msg):
                analysis_jobs[job_id]["progress"] = pct
                analysis_jobs[job_id]["message"] = msg

            res = splitter.analyze_service(
                audio_path=p,
                min_sermon_minutes=req.min_sermon_minutes,
                density_threshold=req.density_threshold,
                gap_tolerance=req.gap_tolerance,
                padding_seconds=req.padding_seconds,
                progress_callback=cb
            )
            analysis_jobs[job_id]["status"] = "completed"
            analysis_jobs[job_id]["progress"] = 1.0
            analysis_jobs[job_id]["message"] = "Analysis finished!"
            analysis_jobs[job_id]["result"] = {
                "sermon_start": res.sermon_start,
                "sermon_end": res.sermon_end,
                "sermon_duration": res.sermon_duration,
                "total_duration": res.total_duration,
                "confidence": res.confidence,
                "worship_segments": res.worship_segments,
                "timeline_density": res.timeline_density,
                "segments": res.segments,
                "transcript_text": res.transcript_text,
                "sermon_transcript": res.sermon_transcript
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            analysis_jobs[job_id]["status"] = "failed"
            analysis_jobs[job_id]["error"] = str(e)

    background_tasks.add_task(run_analysis)
    return {"job_id": job_id}

@app.get("/api/analyze-status/{job_id}")
async def get_analysis_status(job_id: str):
    if job_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return analysis_jobs[job_id]

@app.post("/api/export")
async def export_audio(req: ExportRequest):
    input_path = Path(req.audio_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    output_dir = Path(req.output_dir)
    try:
        splitter = ChurchAudioSplitter()
        summary = splitter.export_splits(
            input_audio_path=input_path,
            output_dir=output_dir,
            sermon_start=req.sermon_start,
            sermon_end=req.sermon_end,
            combine_worship=req.combine_worship,
            export_transcript=req.export_transcript,
            sermon_transcript=req.sermon_transcript or "",
            custom_base_name=req.custom_base_name,
            metadata=req.metadata,
            cover_art_path=req.cover_art_path or current_cover_art_path,
            normalize_loudness=req.normalize_loudness,
            export_mp3=req.export_mp3
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/detect-songs")
async def detect_songs_endpoint(req: DetectSongsRequest):
    p = Path(req.audio_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    try:
        splitter = ChurchAudioSplitter()
        songs = splitter.detect_worship_songs(p, worship_end_sec=req.worship_end)
        return {"songs": songs}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export-tracks")
async def export_tracks_endpoint(req: MultiTrackExportRequest):
    input_path = Path(req.audio_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    output_dir = Path(req.output_dir)
    try:
        splitter = ChurchAudioSplitter()
        tracks_data = [t.dict() for t in req.tracks]
        summary = splitter.export_custom_tracks(
            input_audio_path=input_path,
            output_dir=output_dir,
            tracks=tracks_data,
            custom_base_name=req.custom_base_name,
            metadata=req.metadata,
            cover_art_path=req.cover_art_path or current_cover_art_path,
            normalize_loudness=req.normalize_loudness,
            export_mp3=req.export_mp3
        )
        return summary
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/resplit-single-track")
async def resplit_single_track(req: ResplitTrackRequest):
    src = Path(req.source_audio_path)
    dst = Path(req.output_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Source audio file not found")
    try:
        lossless_cut(
            input_path=src,
            output_path=dst,
            start_sec=req.start,
            end_sec=req.end,
            metadata=req.metadata,
            cover_art_path=req.cover_art_path or current_cover_art_path,
            normalize_loudness=req.normalize_loudness
        )
        info = get_audio_info(dst)
        return {
            "status": "success",
            "path": str(dst.resolve()),
            "duration": info["duration"],
            "formatted_range": f"{format_timestamp(req.start)} - {format_timestamp(req.end)}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-cover-art")
async def upload_cover_art(file: UploadFile = File(...)):
    global current_cover_art_path
    upload_dir = Path(os.environ.get("TEMP", "/tmp")) / "church_audio_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix.lower() or ".jpg"
    target_path = upload_dir / f"cover_art{ext}"

    with open(target_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    current_cover_art_path = str(target_path.resolve())
    return {
        "status": "success",
        "path": current_cover_art_path,
        "filename": file.filename,
        "url": "/api/cover-art"
    }

@app.get("/api/cover-art")
async def get_cover_art():
    global current_cover_art_path
    if current_cover_art_path and Path(current_cover_art_path).exists():
        media_type = "image/png" if current_cover_art_path.endswith(".png") else "image/jpeg"
        return FileResponse(current_cover_art_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="No cover art uploaded")

@app.post("/api/extract-sermon-info")
async def extract_sermon_info_endpoint(req: ExtractSermonInfoRequest):
    try:
        summary = generate_social_summary(
            transcript=req.transcript,
            title=req.title,
            preacher=req.preacher,
            series=req.series,
            service_type=req.service_type
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watcher/status")
async def get_watcher_status():
    global active_watcher
    if active_watcher is None:
        return {
            "is_running": False,
            "status": "stopped",
            "watch_folder": "",
            "output_folder": "",
            "logs": []
        }
    return active_watcher.get_status()

@app.post("/api/watcher/start")
async def start_watcher(req: WatcherStartRequest):
    global active_watcher, current_cover_art_path
    if active_watcher and active_watcher._running:
        active_watcher.stop()

    active_watcher = ChurchAudioWatcher(
        watch_folder=req.watch_folder,
        output_folder=req.output_folder,
        default_preacher=req.default_preacher or "",
        default_series=req.default_series or "",
        default_genre=req.default_genre or "Sermon",
        cover_art_path=req.cover_art_path or current_cover_art_path,
        normalize_loudness=req.normalize_loudness,
        export_mp3=req.export_mp3,
        model_size=req.model_size
    )
    active_watcher.start()
    return active_watcher.get_status()

@app.post("/api/watcher/stop")
async def stop_watcher():
    global active_watcher
    if active_watcher:
        active_watcher.stop()
        return active_watcher.get_status()
    return {"is_running": False, "status": "stopped"}

@app.post("/api/load-split-summary")
async def load_split_summary(req: LoadSummaryRequest):
    p = Path(req.folder_path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    
    summary_files = list(p.glob("*_summary.json"))
    if summary_files:
        with open(summary_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    
    audio_files = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in [".mp3", ".wav", ".m4a"]:
            info = get_audio_info(f)
            audio_files.append({
                "label": f.stem,
                "filename": f.name,
                "path": str(f.resolve()),
                "duration": info["duration"],
                "formatted_range": format_timestamp(info["duration"])
            })
    return {"files": audio_files, "source_file": str(p)}

@app.get("/api/audio-stream")
async def stream_audio(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    # Stream for local preview
    media_type = "audio/mpeg" if p.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(str(p), media_type=media_type)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Church Audio Splitter UI loading...</h1>")
