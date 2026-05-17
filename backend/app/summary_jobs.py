"""In-memory store for AI-summary tasks.

Lives alongside ``jobs.py`` (download jobs) so the two domains don't
share state. Each ``SummaryJob`` carries:

- pipeline status (``stage`` + human-readable ``stage_msg`` + ``percent``)
- the source of truth so far (transcript, accumulated summary markdown)
- a per-job event queue used by the SSE route to push deltas to the
  browser without blocking the worker thread
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# Sentinel pushed onto a job's event queue to tell SSE consumers
# "the stream is over, close the connection".
EVENT_END = object()


@dataclass
class SummaryJob:
    id: str
    url: str
    stage: str = "queued"       # queued|fetching_meta|fetching_subtitle|downloading_audio|transcribing|summarizing|finished|error
    stage_msg: str = "等待开始"   # human-readable, shown in UI
    percent: float = 0.0         # 0..100, optional
    meta: Optional[Dict[str, Any]] = None  # video meta: title, thumbnail, duration, uploader
    source: Optional[str] = None  # "subtitle" | "asr"
    language: Optional[str] = None
    transcript: Optional[list] = None  # [{start, end, text}]
    summary_md: str = ""         # accumulated markdown from the LLM
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    # Event queue for the SSE stream. Each item is either:
    #   (event_name: str, data: dict)            # message to forward
    #   EVENT_END                                 # close the stream
    events: "queue.Queue[Any]" = field(default_factory=queue.Queue)


class SummaryJobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, SummaryJob] = {}
        self._lock = threading.Lock()
        self._cap = 64  # MVP: keep last N in memory, evict oldest

    def create(self, url: str) -> SummaryJob:
        job_id = uuid.uuid4().hex[:12]
        job = SummaryJob(id=job_id, url=url)
        with self._lock:
            if len(self._jobs) >= self._cap:
                # evict oldest to keep memory bounded
                oldest_id = min(self._jobs, key=lambda k: self._jobs[k].created_at)
                self._jobs.pop(oldest_id, None)
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[SummaryJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def remove(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


summary_jobs = SummaryJobManager()


def emit(job: SummaryJob, event: str, **data: Any) -> None:
    """Atomically update job fields *and* push an SSE event."""
    # Snapshot updates we apply directly on the job for the polling
    # consumer (in case SSE was never opened, the user can still GET
    # the final state from /api/summarize/{id}).
    if event == "stage":
        job.stage = data.get("stage", job.stage)
        job.stage_msg = data.get("message", job.stage_msg)
        if "percent" in data and data["percent"] is not None:
            job.percent = float(data["percent"])
    elif event == "meta":
        job.meta = data.get("meta") or job.meta
    elif event == "source":
        job.source = data.get("source") or job.source
        job.language = data.get("language") or job.language
    elif event == "transcript":
        job.transcript = data.get("transcript")
    elif event == "delta":
        chunk = data.get("chunk") or ""
        job.summary_md += chunk
    elif event == "done":
        job.summary_md = data.get("summary_md", job.summary_md)
        job.stage = "finished"
        job.stage_msg = "总结完成"
        job.percent = 100.0
        job.finished_at = time.time()
    elif event == "error":
        job.stage = "error"
        job.stage_msg = "失败"
        job.error = data.get("error") or "未知错误"
        job.finished_at = time.time()

    job.events.put((event, data))


def end_stream(job: SummaryJob) -> None:
    job.events.put(EVENT_END)
