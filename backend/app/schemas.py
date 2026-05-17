from typing import List, Optional

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    url: str = Field(..., description="Video URL to parse")


class FormatInfo(BaseModel):
    format_id: str
    ext: Optional[str] = None
    resolution: Optional[str] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    filesize: Optional[int] = None
    tbr: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    note: Optional[str] = None
    is_audio_only: bool = False
    is_video_only: bool = False
    quicktime_friendly: bool = True


class ParseResponse(BaseModel):
    id: Optional[str] = None
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    extractor: Optional[str] = None
    webpage_url: Optional[str] = None
    view_count: Optional[int] = None
    formats: List[FormatInfo] = []
    ffmpeg_available: bool = True
    max_height: int = 0
    cookies_configured: bool = False
    hd_hint: Optional[str] = None


class DownloadRequest(BaseModel):
    url: str
    format_id: Optional[str] = Field(
        default=None,
        description="yt-dlp format id; if omitted, downloads best quality.",
    )
    audio_only: bool = False


class DownloadResponse(BaseModel):
    job_id: str


class ProgressResponse(BaseModel):
    job_id: str
    status: str
    percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None
    filename: Optional[str] = None
    error: Optional[str] = None


# --- AI summary ---------------------------------------------------------


class SummarizeRequest(BaseModel):
    url: str = Field(..., description="Video URL to summarize")


class SummarizeResponse(BaseModel):
    task_id: str


class SummaryVideoMeta(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    extractor: Optional[str] = None
    webpage_url: Optional[str] = None


class SummaryStatusResponse(BaseModel):
    id: str
    stage: str
    stage_msg: str
    percent: float = 0.0
    meta: Optional[SummaryVideoMeta] = None
    source: Optional[str] = None  # "subtitle" | "asr"
    language: Optional[str] = None
    summary_md: str = ""
    transcript_count: int = 0
    error: Optional[str] = None
