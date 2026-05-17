"""Video parse / download orchestration.

Strategy:
- For Douyin we use our own zero-dependency extractor (no cookies, no
  signing, no ffmpeg) because yt-dlp's DouyinIE needs `s_v_web_id` cookies
  the user shouldn't have to provide.
- For every other site we fall back to yt-dlp's library API.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .ffmpeg_check import ffmpeg_available, ffmpeg_path
from .jobs import jobs
from .platforms import douyin
from .url_normalizer import normalize_url

# Project-wide download root (created on demand).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_ROOT = BACKEND_ROOT / "downloads"
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)


# --- parse ---------------------------------------------------------------


def _format_friendly(f: Dict[str, Any]) -> Dict[str, Any]:
    """Pick fields the frontend actually needs and infer is_audio/video_only."""
    vcodec = f.get("vcodec") or "none"
    acodec = f.get("acodec") or "none"
    return {
        "format_id": f.get("format_id"),
        "ext": f.get("ext"),
        "resolution": f.get("resolution") or (
            f"{f.get('width')}x{f.get('height')}"
            if f.get("width") and f.get("height")
            else None
        ),
        "height": f.get("height"),
        "fps": f.get("fps"),
        "filesize": f.get("filesize") or f.get("filesize_approx"),
        "tbr": f.get("tbr"),
        "vcodec": None if vcodec == "none" else vcodec,
        "acodec": None if acodec == "none" else acodec,
        "note": f.get("format_note"),
        "is_audio_only": vcodec == "none" and acodec != "none",
        "is_video_only": acodec == "none" and vcodec != "none",
    }


# In-memory cache keyed by source URL → {format_id: {direct_url, referer, title}}.
# Lets _run_douyin_download skip re-parsing the share page when the user
# clicks "download" right after parse. Bounded to a soft 64 entries so we
# don't grow unbounded across a long-running server.
_DOUYIN_PLAN_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}
_DOUYIN_PLAN_LOCK = threading.Lock()
_DOUYIN_PLAN_CAP = 64


def _remember_douyin_plan(
    url: str, title: str, formats: List[Dict[str, Any]]
) -> None:
    by_id = {
        f["format_id"]: {
            "direct_url": f["_direct_url"],
            "referer": f["_referer"],
            "title": title,
        }
        for f in formats
    }
    with _DOUYIN_PLAN_LOCK:
        if len(_DOUYIN_PLAN_CACHE) >= _DOUYIN_PLAN_CAP:
            # Drop the oldest entry (insertion order in dict).
            try:
                _DOUYIN_PLAN_CACHE.pop(next(iter(_DOUYIN_PLAN_CACHE)))
            except StopIteration:
                pass
        _DOUYIN_PLAN_CACHE[url] = by_id


def _lookup_douyin_plan(url: str, format_id: Optional[str]) -> Optional[Dict[str, Any]]:
    with _DOUYIN_PLAN_LOCK:
        plans = _DOUYIN_PLAN_CACHE.get(url)
    if not plans:
        return None
    if format_id and format_id in plans:
        return plans[format_id]
    return next(iter(plans.values()), None)


def _parse_douyin(url: str) -> Dict[str, Any]:
    meta, formats = douyin.fetch(url)
    public_formats = [
        {k: v for k, v in f.items() if not k.startswith("_")} for f in formats
    ]
    _remember_douyin_plan(url, meta["title"], formats)
    return {
        **meta,
        "formats": public_formats,
        # Douyin path doesn't actually need ffmpeg, but we keep this flag so
        # the rest of the UI can still react to host capability uniformly.
        "ffmpeg_available": ffmpeg_available(),
    }


def _parse_with_ytdlp(url: str) -> Dict[str, Any]:
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        info = ydl.sanitize_info(info)

    formats_raw: List[Dict[str, Any]] = info.get("formats") or []
    formats = [_format_friendly(f) for f in formats_raw if f.get("format_id")]

    has_ffmpeg = ffmpeg_available()
    if not has_ffmpeg:
        # Without ffmpeg we can't mux video-only with audio-only, so hide
        # those streams; the user can still grab anything pre-muxed plus
        # audio-only formats.
        formats = [f for f in formats if not f["is_video_only"]]

    def _sort_key(f: Dict[str, Any]):
        kind = 0 if (not f["is_audio_only"] and not f["is_video_only"]) else (
            1 if f["is_video_only"] else 2
        )
        height = -(f.get("height") or 0)
        tbr = -(f.get("tbr") or 0)
        return (kind, height, tbr)

    formats.sort(key=_sort_key)

    return {
        "id": info.get("id"),
        "title": info.get("title") or "Untitled",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "webpage_url": info.get("webpage_url") or url,
        "view_count": info.get("view_count"),
        "formats": formats,
        "ffmpeg_available": has_ffmpeg,
    }


def parse_video(url: str) -> Dict[str, Any]:
    url = normalize_url(url)
    if douyin.is_douyin_url(url):
        return _parse_douyin(url)
    return _parse_with_ytdlp(url)


# --- error humanization --------------------------------------------------


def _friendly_error(msg: str) -> str:
    """Map a couple of well-known yt-dlp error strings to actionable Chinese
    hints. Falls back to the original message when nothing matches."""
    low = msg.lower()
    if "ffmpeg is not installed" in low or "ffmpeg is not found" in low:
        return (
            "服务器暂未配置高清合并能力，已自动改下兼容画质。"
            "如需 1080p+ 原画质，请联系管理员在服务器执行 `brew install ffmpeg`。"
        )
    if "fresh cookies" in low or "cookies are needed" in low or "this video requires login" in low:
        return "平台临时升级了反爬，正在尝试备选解析路径，请稍后再试一次。"
    if "unsupported url" in low:
        return (
            "暂不支持该链接：请直接复制视频详情页链接（如 `…/video/数字`）后再试。"
        )
    if "private video" in low or "login required" in low or "sign in" in low:
        return "该视频需要登录或仅作者可见，无法直接下载。"
    if "geoip" in low or "geo restrict" in low or "not available in your country" in low:
        return "该视频在当前网络所在地区不可观看，请尝试更换网络环境。"
    return msg


# --- download (yt-dlp branch) --------------------------------------------


def _make_progress_hook(job_id: str):
    def hook(d: Dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            percent = (downloaded / total * 100.0) if total else 0.0
            jobs.update(
                job_id,
                status="downloading",
                percent=round(percent, 2),
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed=d.get("speed"),
                eta=d.get("eta"),
                filename=d.get("filename"),
            )
        elif status == "finished":
            # yt-dlp emits "finished" after each fragment; muxing may still
            # be running. Mark as post-processing so the UI doesn't flash 100%
            # too early.
            jobs.update(
                job_id,
                status="processing",
                percent=99.0,
                filename=d.get("filename"),
            )
        elif status == "error":
            jobs.update(job_id, status="error", error="yt-dlp reported error")

    return hook


def _run_ytdlp_download(
    job_id: str, url: str, format_id: Optional[str], audio_only: bool
) -> None:
    job_dir = DOWNLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(job_dir / "%(title).80B.%(ext)s")
    has_ffmpeg = ffmpeg_available()

    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "progress_hooks": [_make_progress_hook(job_id)],
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "fragment_retries": 3,
    }
    # If ffmpeg lives in imageio-ffmpeg's site-packages rather than on PATH,
    # yt-dlp won't auto-find it. We point at it explicitly when available.
    ff = ffmpeg_path()
    if ff:
        ydl_opts["ffmpeg_location"] = ff

    if audio_only:
        if has_ffmpeg:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    elif format_id:
        if has_ffmpeg:
            ydl_opts["format"] = f"{format_id}+bestaudio/best/{format_id}"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = (
                f"{format_id}[acodec!=none]"
                "/best[ext=mp4][acodec!=none]/best[acodec!=none]"
            )
    else:
        if has_ffmpeg:
            ydl_opts["format"] = "bestvideo+bestaudio/best"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "best[ext=mp4][acodec!=none]/best[acodec!=none]"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            info = ydl.sanitize_info(info)
            final_path: Optional[str] = None
            if "requested_downloads" in info and info["requested_downloads"]:
                final_path = info["requested_downloads"][0].get("filepath")
            if not final_path:
                final_path = info.get("filepath") or info.get("_filename")
            if not final_path:
                files = [p for p in job_dir.glob("*") if p.is_file()]
                if files:
                    final_path = str(max(files, key=lambda p: p.stat().st_size))

        jobs.update(
            job_id,
            status="finished",
            percent=100.0,
            filename=final_path,
        )
    except DownloadError as e:
        jobs.update(job_id, status="error", error=_friendly_error(str(e)))
    except Exception as e:  # noqa: BLE001
        jobs.update(job_id, status="error", error=_friendly_error(f"{type(e).__name__}: {e}"))


# --- download (Douyin direct branch) -------------------------------------


_INVALID_FS_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def _safe_filename(title: str, ext: str = "mp4", max_len: int = 80) -> str:
    """Sanitize an arbitrary video title into a filesystem-safe stem."""
    cleaned = _INVALID_FS_CHARS.sub(" ", title or "video").strip() or "video"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return f"{cleaned}.{ext}"


def _resolve_douyin_target(
    url: str, format_id: Optional[str], audio_only: bool
) -> Tuple[str, str, str]:
    """Return `(direct_url, referer, title)` for a Douyin download.

    If parse_video() previously stashed a plan for this URL we reuse it;
    otherwise we re-parse the share page on the fly. The audio_only flag
    has no effect here — Douyin's share JSON doesn't ship a standalone
    audio asset, so audio mode downloads the mp4 and lets the client
    extract audio if needed.
    """
    del audio_only  # accepted for API symmetry, not used

    cached = _lookup_douyin_plan(url, format_id)
    if cached:
        return cached["direct_url"], cached["referer"], cached["title"]

    meta, formats = douyin.fetch(url)
    if not formats:
        raise RuntimeError("解析成功但抖音没有返回可下载的视频流。")

    _remember_douyin_plan(url, meta["title"], formats)
    if format_id:
        chosen = next((f for f in formats if f["format_id"] == format_id), formats[0])
    else:
        chosen = formats[0]
    return chosen["_direct_url"], chosen["_referer"], meta["title"]


def _run_douyin_download(
    job_id: str, url: str, format_id: Optional[str], audio_only: bool
) -> None:
    job_dir = DOWNLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        direct_url, referer, title = _resolve_douyin_target(url, format_id, audio_only)
    except (urllib.error.URLError, ValueError, RuntimeError) as e:
        jobs.update(job_id, status="error", error=_friendly_error(f"{type(e).__name__}: {e}"))
        return

    target_path = job_dir / _safe_filename(title, ext="mp4")

    headers = {
        "User-Agent": douyin.MOBILE_UA,
        "Referer": referer,
        "Accept": "*/*",
    }

    jobs.update(job_id, status="downloading", percent=0.0, filename=str(target_path))

    last_update = 0.0
    last_bytes = 0
    started = time.monotonic()
    chunk_size = 256 * 1024

    try:
        req = urllib.request.Request(direct_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            total: Optional[int] = None
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                total = int(cl)

            downloaded = 0
            with open(target_path, "wb") as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)

                    # Throttle progress writes so we don't hammer the lock
                    # on small chunk boundaries.
                    now = time.monotonic()
                    if now - last_update >= 0.25 or (total and downloaded == total):
                        elapsed = max(now - started, 0.001)
                        speed = (downloaded - last_bytes) / max(now - last_update, 0.001)
                        eta = int((total - downloaded) / speed) if (total and speed > 0) else None
                        jobs.update(
                            job_id,
                            status="downloading",
                            percent=round((downloaded / total * 100.0) if total else 0.0, 2),
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                            speed=speed if speed > 0 else None,
                            eta=eta,
                            filename=str(target_path),
                        )
                        last_update = now
                        last_bytes = downloaded
                        _ = elapsed  # keep mypy quiet; computed for future use

        jobs.update(
            job_id,
            status="finished",
            percent=100.0,
            filename=str(target_path),
        )
    except (urllib.error.URLError, OSError) as e:
        jobs.update(job_id, status="error", error=_friendly_error(f"{type(e).__name__}: {e}"))


# --- public download entrypoint ------------------------------------------


def _run_download(job_id: str, url: str, format_id: Optional[str], audio_only: bool) -> None:
    url = normalize_url(url)
    if douyin.is_douyin_url(url):
        _run_douyin_download(job_id, url, format_id, audio_only)
    else:
        _run_ytdlp_download(job_id, url, format_id, audio_only)


def start_download(url: str, format_id: Optional[str], audio_only: bool = False) -> str:
    job = jobs.create(url=url, format_id=format_id)
    t = threading.Thread(
        target=_run_download,
        args=(job.id, url, format_id, audio_only),
        daemon=True,
    )
    t.start()
    return job.id


def cleanup_job(job_id: str) -> None:
    job_dir = DOWNLOAD_ROOT / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    jobs.remove(job_id)
