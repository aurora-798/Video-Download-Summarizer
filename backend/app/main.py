"""FastAPI entrypoint for the universal video downloader."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Empty
from typing import Iterator

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .downloader import _friendly_error, cleanup_job, parse_video, start_download
from .ffmpeg_check import ffmpeg_available, ffmpeg_status
from .jobs import jobs
from .llm_client import describe_config as llm_describe
from .schemas import (
    DownloadRequest,
    DownloadResponse,
    ParseRequest,
    ParseResponse,
    ProgressResponse,
    SummarizeRequest,
    SummarizeResponse,
    SummaryStatusResponse,
    SummaryVideoMeta,
)
from .summarizer import get_summary_meta, start_summary
from .summary_jobs import EVENT_END, summary_jobs
from .transcriber import describe_backend as whisper_describe

# Load .env once at import time so OPENAI_API_KEY / WHISPER_* are visible
# to the rest of the app. ``python-dotenv`` is optional — we tolerate its
# absence so the download-only feature keeps working without a key.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:  # pragma: no cover
    pass

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if ffmpeg_available():
        logger.info("ffmpeg ready — video+audio merge enabled for DASH sites (e.g. Bilibili)")
    else:
        logger.warning(
            "ffmpeg not found: Bilibili/YouTube may only expose audio in /api/parse. "
            "Run: pip install -r requirements.txt  (includes imageio-ffmpeg)"
        )
    yield


app = FastAPI(
    title="Universal Video Downloader",
    description="Thin FastAPI wrapper over yt-dlp.",
    version="0.1.0",
    lifespan=lifespan,
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
    return {
        "ok": True,
        "ffmpeg": ffmpeg_status(),
        "summary": {
            "llm": llm_describe(),
            "whisper": whisper_describe(),
        },
    }


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


# --- AI summary -----------------------------------------------------------


@app.post("/api/summarize", response_model=SummarizeResponse)
def api_summarize(req: SummarizeRequest) -> SummarizeResponse:
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="url is required")
    task_id = start_summary(req.url.strip())
    return SummarizeResponse(task_id=task_id)


@app.get("/api/summarize/{task_id}", response_model=SummaryStatusResponse)
def api_summary_status(task_id: str) -> SummaryStatusResponse:
    job = summary_jobs.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="summary task not found")
    snapshot = get_summary_meta(job)
    meta = snapshot.get("meta")
    return SummaryStatusResponse(
        id=snapshot["id"],
        stage=snapshot["stage"],
        stage_msg=snapshot["stage_msg"],
        percent=snapshot["percent"],
        meta=SummaryVideoMeta(**meta) if meta else None,
        source=snapshot.get("source"),
        language=snapshot.get("language"),
        summary_md=snapshot.get("summary_md") or "",
        transcript_count=snapshot.get("transcript_count") or 0,
        error=snapshot.get("error"),
    )


@app.get("/api/summarize/{task_id}/stream")
def api_summary_stream(task_id: str) -> StreamingResponse:
    """Server-sent events: pushes the worker's events as they happen.

    Event names: ``stage``, ``meta``, ``source``, ``transcript``,
    ``delta``, ``done``, ``error``. The stream auto-closes after ``done``
    or ``error``. Clients can reconnect via the polling endpoint above.
    """
    job = summary_jobs.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="summary task not found")

    def _gen() -> Iterator[bytes]:
        # First push: replay everything we already know so a late-joining
        # client doesn't miss the meta/source we emitted before the SSE
        # connection was opened.
        snapshot = get_summary_meta(job)
        yield _sse_pack("snapshot", snapshot)

        while True:
            try:
                item = job.events.get(timeout=30.0)
            except Empty:
                # heartbeat keeps the connection alive through proxies
                yield b": keep-alive\n\n"
                continue
            if item is EVENT_END:
                yield _sse_pack("close", {"reason": "stream ended"})
                break
            event_name, data = item
            yield _sse_pack(event_name, data)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


def _sse_pack(event: str, data: object) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


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
