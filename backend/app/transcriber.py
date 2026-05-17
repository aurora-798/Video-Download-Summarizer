"""Audio-to-text transcription with two interchangeable backends.

The summarizer falls back here whenever no platform subtitle is
available (i.e. Douyin, 小红书, Bilibili-guest, …). We support two
backends, picked by env at call time:

  WHISPER_BACKEND=local   (default)
      Uses faster-whisper running on the local CPU/GPU. Model name set
      by WHISPER_MODEL (default ``base``). First call downloads the
      model (~70 MB for ``base``, ~250 MB for ``small``) into the
      Hugging Face cache.

  WHISPER_BACKEND=api
      POST the audio to an OpenAI-compatible ``/audio/transcriptions``
      endpoint. Configure with:
          WHISPER_BASE_URL   e.g. https://api.siliconflow.cn/v1
          WHISPER_API_KEY    bearer token
          WHISPER_API_MODEL  e.g. FunAudioLLM/SenseVoiceSmall

Both backends return the same shape so the rest of the pipeline doesn't
care which one ran::

    [{"start": 0.0, "end": 3.2, "text": "..."}]
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("summarizer.transcriber")

ProgressFn = Callable[[str, Optional[float]], None]
# A simple progress callback: (stage_label, optional 0..100 percent).

_LOCAL_MODEL_LOCK = threading.Lock()
_LOCAL_MODEL: Any = None  # cached faster_whisper.WhisperModel


def _backend() -> str:
    return (os.getenv("WHISPER_BACKEND") or "local").strip().lower()


def _has_api_config() -> bool:
    return bool(os.getenv("WHISPER_API_KEY") and os.getenv("WHISPER_BASE_URL"))


def transcribe(
    audio_path: str | Path,
    *,
    language: Optional[str] = None,
    progress: Optional[ProgressFn] = None,
    vad_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Transcribe ``audio_path`` and return timestamped segments."""
    path = Path(audio_path)
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"audio file missing or empty: {path}")

    backend = _backend()
    if backend == "api":
        if not _has_api_config():
            raise RuntimeError(
                "WHISPER_BACKEND=api 但缺少 WHISPER_API_KEY/WHISPER_BASE_URL。"
                "请在 backend/.env 中配置，或改回 WHISPER_BACKEND=local。"
            )
        return _transcribe_api(path, language=language, progress=progress)
    return _transcribe_local(
        path, language=language, progress=progress, vad_filter=vad_filter
    )


# --- local: faster-whisper -----------------------------------------------


def _load_local_model() -> Any:
    """Lazy-load the faster-whisper model. Thread-safe singleton."""
    global _LOCAL_MODEL
    if _LOCAL_MODEL is not None:
        return _LOCAL_MODEL
    with _LOCAL_MODEL_LOCK:
        if _LOCAL_MODEL is not None:
            return _LOCAL_MODEL
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "未安装 faster-whisper。请执行：\n"
                "    pip install -r backend/requirements.txt\n"
                "或改用 API 转写：在 .env 设 WHISPER_BACKEND=api"
            ) from exc

        model_size = os.getenv("WHISPER_MODEL") or "base"
        device = os.getenv("WHISPER_DEVICE") or "cpu"
        # int8 keeps memory low on CPU; float16 is fine on Apple Silicon GPU.
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE") or (
            "float16" if device != "cpu" else "int8"
        )
        logger.info(
            "loading faster-whisper model=%s device=%s compute=%s",
            model_size, device, compute_type,
        )
        _LOCAL_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
        return _LOCAL_MODEL


def _transcribe_local(
    path: Path,
    *,
    language: Optional[str],
    progress: Optional[ProgressFn],
    vad_filter: Optional[bool],
) -> List[Dict[str, Any]]:
    if progress:
        progress("loading_whisper_model", None)
    model = _load_local_model()

    if progress:
        progress("transcribing", 0.0)

    # VAD trims silence for podcasts, but music / some m4a streams (e.g.
    # Bilibili DASH audio) can be misclassified as non-speech → 0 segments.
    attempts: list[bool]
    if vad_filter is None:
        attempts = [True, False]
    else:
        attempts = [vad_filter]

    out: List[Dict[str, Any]] = []
    info_duration = 0.0
    info_lang: Optional[str] = None
    for idx, use_vad in enumerate(attempts):
        segments_iter, info = model.transcribe(
            str(path),
            language=language,  # None → auto-detect
            vad_filter=use_vad,
            vad_parameters={"min_silence_duration_ms": 500} if use_vad else None,
            beam_size=1,
        )
        total = max(info.duration or 1.0, 1.0)
        info_duration = info.duration or 0.0
        info_lang = info.language

        out = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if not text:
                continue
            out.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
            })
            if progress:
                pct = min(99.0, (seg.end or 0) / total * 100.0)
                progress("transcribing", pct)

        if out:
            if idx > 0:
                logger.warning(
                    "VAD returned 0 segments for %s; retried with vad_filter=False → %d segments",
                    path.name, len(out),
                )
            break
        if use_vad and len(attempts) > 1:
            logger.warning(
                "VAD returned 0 segments for %s (%.1fs); retrying without VAD",
                path.name, info_duration,
            )
            if progress:
                progress("transcribing", 0.0)

    if progress:
        progress("transcribing", 100.0)
    logger.info(
        "local transcription done: %d segments, %.1fs audio, detected lang=%s",
        len(out), info_duration, info_lang,
    )
    return out


# --- remote: OpenAI-compatible /audio/transcriptions ----------------------


def _transcribe_api(
    path: Path, *, language: Optional[str], progress: Optional[ProgressFn]
) -> List[Dict[str, Any]]:
    import httpx  # local import: only the API backend needs it

    base = (os.getenv("WHISPER_BASE_URL") or "").rstrip("/")
    key = os.getenv("WHISPER_API_KEY") or ""
    model = os.getenv("WHISPER_API_MODEL") or "whisper-1"
    url = f"{base}/audio/transcriptions"

    if progress:
        progress("uploading_audio", None)

    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "audio/mpeg")}
        data: Dict[str, Any] = {
            "model": model,
            # verbose_json gives us per-segment timestamps. Standard OpenAI
            # supports this; SiliconFlow / Groq also accept it (segments
            # may be empty for some models — we degrade gracefully below).
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }
        if language:
            data["language"] = language
        resp = httpx.post(
            url,
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {key}"},
            timeout=600.0,
        )
    resp.raise_for_status()
    body = resp.json()

    if progress:
        progress("transcribing", 100.0)

    segments = body.get("segments") or []
    out: List[Dict[str, Any]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "start": round(float(seg.get("start") or 0.0), 2),
            "end": round(float(seg.get("end") or 0.0), 2),
            "text": text,
        })

    # Some endpoints only return ``text`` without segments. Synthesize a
    # single cue so the rest of the pipeline still works (no chapter
    # timestamps in that case).
    if not out and body.get("text"):
        out.append({"start": 0.0, "end": 0.0, "text": str(body["text"]).strip()})

    logger.info("api transcription done: %d segments", len(out))
    return out


def describe_backend() -> Dict[str, Any]:
    """For /api/health style introspection."""
    if _backend() == "api":
        return {
            "backend": "api",
            "configured": _has_api_config(),
            "base_url": os.getenv("WHISPER_BASE_URL"),
            "model": os.getenv("WHISPER_API_MODEL") or "whisper-1",
        }
    return {
        "backend": "local",
        "configured": True,
        "model": os.getenv("WHISPER_MODEL") or "base",
        "device": os.getenv("WHISPER_DEVICE") or "cpu",
    }
