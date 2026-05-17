"""FastAPI entrypoint for the universal video downloader."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .downloader import _friendly_error, cleanup_job, parse_video, start_download
from .ffmpeg_check import ffmpeg_status
from .jobs import jobs
from .schemas import (
    DownloadRequest,
    DownloadResponse,
    ParseRequest,
    ParseResponse,
    ProgressResponse,
)

app = FastAPI(
    title="Universal Video Downloader",
    description="Thin FastAPI wrapper over yt-dlp.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ffmpeg": ffmpeg_status()}


@app.post("/api/parse", response_model=ParseResponse)
def api_parse(req: ParseRequest) -> ParseResponse:
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    try:
        data = parse_video(req.url.strip())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=_friendly_error(str(e))
        ) from e
    return ParseResponse(**data)


@app.post("/api/download", response_model=DownloadResponse)
def api_download(req: DownloadRequest) -> DownloadResponse:
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    job_id = start_download(req.url.strip(), req.format_id, req.audio_only)
    return DownloadResponse(job_id=job_id)


@app.get("/api/progress/{job_id}", response_model=ProgressResponse)
def api_progress(job_id: str) -> ProgressResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return ProgressResponse(
        job_id=job.id,
        status=job.status,
        percent=job.percent,
        downloaded_bytes=job.downloaded_bytes,
        total_bytes=job.total_bytes,
        speed=job.speed,
        eta=job.eta,
        filename=os.path.basename(job.filename) if job.filename else None,
        error=job.error,
    )


@app.get("/api/file/{job_id}")
def api_file(job_id: str, background: BackgroundTasks) -> FileResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "finished" or not job.filename:
        raise HTTPException(status_code=409, detail=f"job not ready (status={job.status})")
    path = Path(job.filename)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file already cleaned up")

    background.add_task(cleanup_job, job_id)
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
