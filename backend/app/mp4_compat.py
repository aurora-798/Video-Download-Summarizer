"""Post-process merged MP4 for macOS QuickTime / Finder compatibility.

Bilibili (and others) often ship AV1 or HEVC tagged as ``hev1``. QuickTime
plays AAC audio but may show a black picture unless we remux (HEVC → ``hvc1``)
or transcode (AV1 → H.264).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Optional

from .ffmpeg_check import ffmpeg_path

logger = logging.getLogger(__name__)

_VIDEO_CODEC_RE = re.compile(
    r"Stream #\d+:\d+.*?: Video: (\w+)", re.MULTILINE
)


def vcodec_family(vcodec: Optional[str]) -> str:
    v = (vcodec or "").lower()
    if v.startswith("avc") or "h264" in v:
        return "h264"
    if v.startswith("hev") or v.startswith("hvc"):
        return "hevc"
    if v.startswith("av01") or v.startswith("av1"):
        return "av1"
    return "other"


def probe_video_codec(path: str) -> Optional[str]:
    ff = ffmpeg_path()
    if not ff:
        return None
    proc = subprocess.run(
        [ff, "-hide_banner", "-i", path],
        capture_output=True,
        text=True,
        check=False,
    )
    m = _VIDEO_CODEC_RE.search(proc.stderr or "")
    return m.group(1).lower() if m else None


def prefer_quicktime_format_id(
    formats: list[dict], format_id: Optional[str]
) -> Optional[str]:
    """If the user picked AV1/HEVC but H.264 exists at the same height, use H.264."""
    if not format_id:
        return format_id
    chosen = next((f for f in formats if f.get("format_id") == format_id), None)
    if chosen and chosen.get("is_audio_only"):
        return format_id

    height = chosen.get("height") if chosen else None
    if height is None:
        return format_id
    if chosen and vcodec_family(chosen.get("vcodec")) == "h264":
        return format_id

    h264_at_height = [
        f
        for f in formats
        if f.get("is_video_only")
        and f.get("height") == height
        and vcodec_family(f.get("vcodec")) == "h264"
    ]
    if not h264_at_height:
        return format_id
    best = max(h264_at_height, key=lambda f: f.get("tbr") or 0)
    return best["format_id"]


def drop_redundant_codecs(formats: list[dict]) -> list[dict]:
    """Hide AV1/HEVC rungs when H.264 exists at the same resolution."""
    by_height: dict[int, list[dict]] = {}
    for f in formats:
        if f.get("is_audio_only") or not f.get("height"):
            continue
        by_height.setdefault(int(f["height"]), []).append(f)

    drop: set[str] = set()
    for group in by_height.values():
        families = {vcodec_family(f.get("vcodec")) for f in group}
        if "h264" not in families:
            continue
        for f in group:
            if vcodec_family(f.get("vcodec")) in ("av1", "hevc"):
                drop.add(f["format_id"])

    return [f for f in formats if f.get("format_id") not in drop]


def ensure_quicktime_compatible(path: str) -> str:
    """Remux or transcode *in place* so QuickTime can play video + audio."""
    ff = ffmpeg_path()
    if not ff or not path or not os.path.isfile(path):
        return path
    if not path.lower().endswith((".mp4", ".m4v", ".mov", ".mkv", ".webm")):
        return path

    codec = probe_video_codec(path)
    if not codec:
        return path

    tmp = f"{path}.qtfix.mp4"
    try:
        if codec == "h264":
            _remux_copy(ff, path, tmp, ["-c", "copy", "-movflags", "+faststart"])
        elif codec == "hevc":
            _remux_copy(
                ff,
                path,
                tmp,
                ["-c", "copy", "-tag:v", "hvc1", "-movflags", "+faststart"],
            )
        elif codec == "av1":
            _transcode_av1_to_h264(ff, path, tmp)
        else:
            _remux_copy(ff, path, tmp, ["-c", "copy", "-movflags", "+faststart"])
        os.replace(tmp, path)
        logger.info("QuickTime fixup applied (%s → compatible mp4)", codec)
    except Exception as exc:  # noqa: BLE001
        logger.warning("QuickTime fixup failed for %s: %s", path, exc)
        if os.path.isfile(tmp):
            os.remove(tmp)
    return path


def _remux_copy(ff: str, src: str, dst: str, extra: list[str]) -> None:
    cmd = [ff, "-y", "-i", src, *extra, dst]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"ffmpeg remux failed: {tail}")


def _transcode_av1_to_h264(ff: str, src: str, dst: str) -> None:
    # Hardware encoder on Apple Silicon / Intel macOS when available.
    hw_cmd = [
        ff,
        "-y",
        "-i",
        src,
        "-c:v",
        "h264_videotoolbox",
        "-b:v",
        "0",
        "-q:v",
        "75",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        dst,
    ]
    proc = subprocess.run(hw_cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return

    sw_cmd = [
        ff,
        "-y",
        "-i",
        src,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        dst,
    ]
    proc = subprocess.run(sw_cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"ffmpeg AV1 transcode failed: {tail}")
