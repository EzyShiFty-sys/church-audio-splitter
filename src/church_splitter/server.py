import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from church_splitter.splitter import ChurchAudioSplitter, format_timestamp
from church_splitter.ffmpeg_utils import get_audio_info, find_ffmpeg

app = FastAPI(title="Church Audio Splitter API")

# Global active jobs store
analysis_jobs: Dict[str, Dict[str, Any]] = {}

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class AnalyzeRequest(BaseModel):
    audio_path: str
    model_size: str = "base"
    min_sermon_minutes: float = 10.0
    density_threshold: float = 0.55
    gap_tolerance: float = 45.0
    padding_seconds: float = 2.0

class ExportRequest(BaseModel):
    audio_path: str
    output_dir: str
    sermon_start: float
    sermon_end: float
    combine_worship: bool = False
    export_transcript: bool = True
    sermon_transcript: Optional[str] = ""
    custom_base_name: Optional[str] = None

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
                "transcript_text": res.transcript_text,
                "sermon_transcript": res.sermon_transcript
            }
        except Exception as e:
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
            custom_base_name=req.custom_base_name
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
