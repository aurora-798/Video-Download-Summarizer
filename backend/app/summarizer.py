"""End-to-end "URL → AI summary" pipeline.

This module ties together:

  1. ``downloader.parse_video()`` — title / thumbnail / duration / etc.
  2. ``subtitle.fetch_subtitle()`` — try platform-native subtitles first
                                     (YouTube, TED, etc.; instant + free)
  3. ``_download_audio_for_url()``  — fallback path: pull the audio file
                                     for Douyin / 小红书 / Bilibili / …
  4. ``transcriber.transcribe()``   — ASR over the audio file
  5. ``llm_client.stream_chat()``   — stream a structured markdown
                                     summary from DeepSeek/etc.

Events are pushed to the job's queue via ``summary_jobs.emit()`` so
``main.py``'s SSE route can forward them to the browser as they happen.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from . import subtitle, transcriber
from .downloader import (
    DOWNLOAD_ROOT,
    _bilibili_formats_for_url,
    _friendly_error,
    _ytdlp_base_opts,
    parse_video,
)
from .ffmpeg_check import ffmpeg_path
from .llm_client import LLMConfigError, stream_chat
from .platforms import bilibili, douyin
from .summary_jobs import SummaryJob, emit, end_stream, summary_jobs
from .url_normalizer import normalize_url

logger = logging.getLogger("summarizer")

# Audio downloads live under DOWNLOAD_ROOT/summaries/<job_id>/ so they
# share the regular cleanup story but stay segregated from user-facing
# download jobs.
SUMMARY_AUDIO_ROOT = DOWNLOAD_ROOT / "summaries"
SUMMARY_AUDIO_ROOT.mkdir(parents=True, exist_ok=True)


# --- public entrypoint ----------------------------------------------------


def start_summary(url: str) -> str:
    """Kick off a background summarizer thread and return the job id."""
    job = summary_jobs.create(url=url)
    t = threading.Thread(target=_run_summary, args=(job.id,), daemon=True)
    t.start()
    return job.id


def _run_summary(job_id: str) -> None:
    job = summary_jobs.get(job_id)
    if not job:
        return
    audio_dir: Optional[Path] = None
    try:
        url = normalize_url(job.url)
        emit(job, "stage", stage="fetching_meta", message="解析视频信息…", percent=2.0)
        meta = _safe_parse_video(url)
        emit(job, "meta", meta=meta)
        emit(job, "stage", stage="fetching_meta", message="已获取视频信息", percent=8.0)

        cues = _try_subtitle(job, url)
        if cues:
            emit(job, "source", source="subtitle", language=job.language or "auto")
        else:
            audio_dir = SUMMARY_AUDIO_ROOT / job.id
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = _download_audio(job, url, audio_dir)
            cues = _do_transcribe(job, audio_path)
            emit(job, "source", source="asr", language=job.language or "auto")

        if not cues:
            raise RuntimeError("未能获得任何字幕或转写文本，无法继续生成总结。")

        emit(job, "transcript", transcript=cues)
        emit(job, "stage", stage="summarizing", message="正在生成 AI 总结…", percent=80.0)
        _stream_llm_summary(job, meta, cues)

        emit(job, "done", summary_md=job.summary_md)
    except LLMConfigError as e:
        emit(job, "error", error=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("summary pipeline failed: %s", e)
        emit(job, "error", error=_friendly_error(f"{type(e).__name__}: {e}"))
    finally:
        end_stream(job)
        # Clean up the temp audio file — we keep transcript/summary in
        # memory for follow-up reads but the raw audio isn't needed.
        if audio_dir and audio_dir.exists():
            shutil.rmtree(audio_dir, ignore_errors=True)


# --- pipeline steps -------------------------------------------------------


def _safe_parse_video(url: str) -> Dict[str, Any]:
    try:
        data = parse_video(url)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"无法解析视频信息：{_friendly_error(str(e))}") from e
    # Keep only the fields the frontend will display.
    return {
        "title": data.get("title") or "未命名视频",
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader"),
        "extractor": data.get("extractor"),
        "webpage_url": data.get("webpage_url") or url,
    }


def _try_subtitle(job: SummaryJob, url: str) -> Optional[List[Dict[str, Any]]]:
    emit(job, "stage", stage="fetching_subtitle", message="尝试获取平台字幕…", percent=12.0)
    sub = subtitle.fetch_subtitle(url)
    if not sub or not sub.get("cues"):
        emit(job, "stage", stage="fetching_subtitle",
             message="该视频无可用字幕，将通过音频转写…", percent=18.0)
        return None
    job.language = sub.get("language")
    emit(job, "stage", stage="fetching_subtitle",
         message=f"已获取 {sub.get('source')} 字幕（{sub.get('language')}）",
         percent=70.0)
    return sub["cues"]


def _do_transcribe(job: SummaryJob, audio_path: Path) -> List[Dict[str, Any]]:
    def _on_progress(stage: str, pct: Optional[float]) -> None:
        if stage == "loading_whisper_model":
            emit(job, "stage", stage="transcribing",
                 message="首次加载语音模型，可能需要 1-2 分钟…", percent=45.0)
        else:
            # Map ASR percent (0..100) into the global 45..75 segment.
            mapped = 45.0 + (pct or 0) * 0.30 if pct is not None else None
            emit(job, "stage", stage="transcribing",
                 message=f"语音转写中… {int(pct) if pct is not None else 0}%",
                 percent=mapped)

    emit(job, "stage", stage="transcribing", message="开始语音转写…", percent=45.0)
    cues = transcriber.transcribe(audio_path, progress=_on_progress)
    if not cues:
        raise RuntimeError("语音转写返回空结果（音频可能无声）。")
    emit(job, "stage", stage="transcribing",
         message=f"转写完成，共 {len(cues)} 段文本", percent=78.0)
    return cues


# --- audio download (no jobs.py coupling) ---------------------------------


def _download_audio(job: SummaryJob, url: str, dest_dir: Path) -> Path:
    """Pull a single audio (or audio-bearing) file for ASR.

    Returns the local path. Uses platform-specific shortcuts where
    available and falls back to ``yt-dlp bestaudio`` otherwise.
    """
    emit(job, "stage", stage="downloading_audio",
         message="下载音频中…", percent=22.0)

    if douyin.is_douyin_url(url):
        return _download_audio_douyin(job, url, dest_dir)
    if bilibili.is_bilibili_url(url):
        return _download_audio_bilibili(job, url, dest_dir)
    return _download_audio_ytdlp(job, url, dest_dir)


def _stream_to_file(
    direct_url: str, dest: Path, *, headers: Dict[str, str],
    job: SummaryJob, start_pct: float = 22.0, end_pct: float = 42.0,
) -> None:
    """urllib chunked download with periodic progress emits."""
    req = urllib.request.Request(direct_url, headers=headers)
    chunk_size = 256 * 1024
    last_update = 0.0
    with urllib.request.urlopen(req, timeout=60) as resp:
        total: Optional[int] = None
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            total = int(cl)
        downloaded = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_update >= 0.5:
                    if total:
                        frac = downloaded / total
                        pct = start_pct + frac * (end_pct - start_pct)
                        emit(job, "stage", stage="downloading_audio",
                             message=f"下载音频中… {downloaded//1024//1024} / {total//1024//1024} MB",
                             percent=pct)
                    last_update = now


def _download_audio_douyin(job: SummaryJob, url: str, dest_dir: Path) -> Path:
    _, formats = douyin.fetch(url)
    if not formats:
        raise RuntimeError("抖音解析失败，未取得视频流。")
    direct_url = formats[0]["_direct_url"]
    referer = formats[0]["_referer"]
    dest = dest_dir / "douyin.mp4"
    _stream_to_file(
        direct_url, dest,
        headers={"User-Agent": douyin.MOBILE_UA, "Referer": referer, "Accept": "*/*"},
        job=job,
    )
    emit(job, "stage", stage="downloading_audio",
         message=f"音频下载完成（{dest.stat().st_size // 1024 // 1024} MB）",
         percent=42.0)
    return dest


def _download_audio_bilibili(job: SummaryJob, url: str, dest_dir: Path) -> Path:
    meta, formats = _bilibili_formats_for_url(url)
    audio = next((f for f in formats if f.get("is_audio_only")), None)
    if not audio:
        # Some single-file legacy videos don't expose an audio-only rung;
        # fall back to the muxed video file (still works for whisper).
        audio = next((f for f in formats if f.get("_muxed")), None) or formats[0]
    direct_url = audio.get("_direct_url") or audio.get("_audio_url")
    if not direct_url:
        raise RuntimeError("B 站音频流缺失。")
    dest = dest_dir / "bilibili.m4a"
    _stream_to_file(
        direct_url, dest,
        headers={
            "User-Agent": bilibili.DESKTOP_UA,
            "Referer": audio.get("_referer") or bilibili.REFERER,
            "Accept": "*/*",
        },
        job=job,
    )
    _ = meta  # title already in job.meta
    emit(job, "stage", stage="downloading_audio",
         message=f"音频下载完成（{dest.stat().st_size // 1024 // 1024} MB）",
         percent=42.0)
    return dest


def _download_audio_ytdlp(job: SummaryJob, url: str, dest_dir: Path) -> Path:
    """Generic path: let yt-dlp pick the best audio format and download.

    We do NOT post-process to mp3 (faster-whisper / ffmpeg can read m4a /
    webm directly), which keeps the path independent of platform.
    """
    outtmpl = str(dest_dir / "audio.%(ext)s")
    ydl_opts: Dict[str, Any] = {
        **_ytdlp_base_opts(
            outtmpl=outtmpl,
            noprogress=True,
            quiet=True,
            no_warnings=True,
            retries=3,
            fragment_retries=3,
            format="bestaudio/best",
        ),
    }
    ff = ffmpeg_path()
    if ff:
        ydl_opts["ffmpeg_location"] = ff

    last_update = [0.0]

    def _hook(d: Dict[str, Any]) -> None:
        if d.get("status") != "downloading":
            return
        now = time.monotonic()
        if now - last_update[0] < 0.5:
            return
        last_update[0] = now
        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if total:
            frac = downloaded / total
            emit(job, "stage", stage="downloading_audio",
                 message=f"下载音频中… {downloaded//1024//1024} / {total//1024//1024} MB",
                 percent=22.0 + frac * 20.0)

    ydl_opts["progress_hooks"] = [_hook]

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
                # Fallback: just pick the largest file in dest_dir.
                files = [p for p in dest_dir.glob("*") if p.is_file()]
                if files:
                    final_path = str(max(files, key=lambda p: p.stat().st_size))
            if not final_path:
                raise RuntimeError("yt-dlp 完成下载但未找到音频文件。")
    except DownloadError as e:
        raise RuntimeError(f"yt-dlp 下载音频失败：{e}") from e

    emit(job, "stage", stage="downloading_audio",
         message="音频下载完成", percent=42.0)
    return Path(final_path)


# --- LLM summarization ----------------------------------------------------


SYSTEM_PROMPT = """你是一位顶级的视频内容分析师，擅长把长视频提炼为结构化的中文笔记。

请基于用户提供的「视频元信息」和「带时间戳的逐字稿」，输出一份高质量的中文 Markdown 总结。

输出必须严格按下面的章节顺序，每个章节用二级标题 `##` 起头：

## 一句话总结
30 字内的核心结论，不要起头废话。

## 内容亮点
用 5 到 8 条 bullet，每条 30-60 字，每条独立的有价值结论。

## 思考与启发
基于视频内容，主动生成 2-4 个有深度的"为什么/如何"问题，并立即给出答案。格式：
- **问：xxx？**
  答：xxx。

## 关键术语
（若视频涉及专业名词才输出本段；否则整段省略）
- **术语**：解释（30 字内）

## 时间线章节
按视频时长合理切分为 3-8 个章节，每章一段。**每章必须用以下严格格式起头**：
- `### [mm:ss] 表情符号 章节标题`
  例如：`### [00:00] ⚙️ 开场与背景介绍`
- 标题下用 80-150 字总结该时段内容。

## 思维导图
输出一段标准 mermaid `mindmap` 语法（仅本段用 ```mermaid 代码块），不超过 3 层深度，根节点是视频主题。例如：
```mermaid
mindmap
  root((视频主题))
    分支1
      子点1
      子点2
    分支2
```

# 重要规则
1. 全程使用中文，即使原视频是英文。
2. 内容要忠于逐字稿，不要编造逐字稿没有的事实。
3. 时间戳必须用 `[mm:ss]` 格式，便于前端识别为可跳转锚点。
4. 不要在开头或结尾添加任何"以下是…"、"总结完毕"之类的多余话。
5. 思维导图必须能被 mermaid 渲染，节点名不要包含特殊字符（括号、引号、冒号等用文字替代）。
"""


def _stream_llm_summary(
    job: SummaryJob, meta: Dict[str, Any], cues: List[Dict[str, Any]]
) -> None:
    transcript_md = _format_transcript_for_llm(cues)
    user_msg = _build_user_message(meta, transcript_md, job.source or "subtitle")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    for piece in stream_chat(messages, temperature=0.3, max_tokens=6000):
        if not piece:
            continue
        emit(job, "delta", chunk=piece)


def _format_transcript_for_llm(cues: List[Dict[str, Any]]) -> str:
    """Compact ``[mm:ss] text`` style for cheap token usage.

    For very long transcripts (>4000 cues) we down-sample by merging
    consecutive cues within the same minute, keeping latency reasonable
    on long podcasts/lectures.
    """
    if not cues:
        return ""
    lines: List[str] = []
    if len(cues) > 4000:
        # Merge by minute.
        bucket_text: List[str] = []
        bucket_min = -1
        for c in cues:
            mm = int(c["start"]) // 60
            if mm != bucket_min:
                if bucket_min >= 0 and bucket_text:
                    lines.append(f"[{_mmss(bucket_min*60)}] " + " ".join(bucket_text))
                bucket_min = mm
                bucket_text = []
            bucket_text.append(c["text"])
        if bucket_text:
            lines.append(f"[{_mmss(bucket_min*60)}] " + " ".join(bucket_text))
    else:
        for c in cues:
            lines.append(f"[{_mmss(c['start'])}] {c['text']}")
    return "\n".join(lines)


def _build_user_message(meta: Dict[str, Any], transcript_md: str, source: str) -> str:
    title = meta.get("title") or "未命名视频"
    duration = meta.get("duration")
    uploader = meta.get("uploader") or "未知作者"
    source_label = "平台原生字幕（高准确度）" if source == "subtitle" else "AI 语音转写（可能有同音字错误，请理解性纠正）"

    dur_label = ""
    if duration:
        total = int(duration)
        dur_label = f"，时长约 {total // 60} 分 {total % 60} 秒"

    return (
        f"# 视频元信息\n"
        f"- 标题：{title}\n"
        f"- 作者：{uploader}{dur_label}\n"
        f"- 文本来源：{source_label}\n\n"
        f"# 带时间戳的逐字稿\n"
        f"{transcript_md}\n"
    )


def _mmss(sec: float) -> str:
    s = int(sec)
    return f"{s // 60:02d}:{s % 60:02d}"


# --- helpers used by main.py ----------------------------------------------


def get_summary_meta(job: SummaryJob) -> Dict[str, Any]:
    """Snapshot of a job for the polling endpoint."""
    return {
        "id": job.id,
        "stage": job.stage,
        "stage_msg": job.stage_msg,
        "percent": round(job.percent, 1),
        "meta": job.meta,
        "source": job.source,
        "language": job.language,
        "summary_md": job.summary_md,
        "transcript_count": len(job.transcript or []),
        "error": job.error,
    }
