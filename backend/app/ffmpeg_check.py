"""Runtime detection of ffmpeg so callers can decide whether multi-stream
merging is available on this host.

Resolution order (first hit wins):
  1) `ffmpeg` on $PATH (e.g. `brew install ffmpeg` already done).
  2) `imageio_ffmpeg.get_ffmpeg_exe()` — a prebuilt static binary that
     `pip install imageio-ffmpeg` ships into site-packages, so the user
     doesn't have to touch their system package manager.

Callers should re-call `ffmpeg_path()` per request rather than cache, so a
newly-pip-installed binary becomes visible without a server restart.
"""

from __future__ import annotations

import os
import shutil
from typing import Optional


def _imageio_ffmpeg_path() -> Optional[str]:
    """Return the bundled static ffmpeg path if imageio-ffmpeg is installed."""
    try:
        import imageio_ffmpeg  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    if path and os.path.isfile(path):
        return path
    return None


def ffmpeg_path() -> Optional[str]:
    """Absolute path to a usable ffmpeg binary, or None."""
    sys_path = shutil.which("ffmpeg")
    if sys_path:
        return sys_path
    return _imageio_ffmpeg_path()


def ffmpeg_available() -> bool:
    return ffmpeg_path() is not None


def ffmpeg_status() -> dict:
    """Frontend-friendly shape: {available, path, hint}."""
    path = ffmpeg_path()
    if path:
        return {"available": True, "path": path, "hint": None}
    return {
        "available": False,
        "path": None,
        "hint": "服务端将自动安装 ffmpeg 静态包，无需用户操作。",
    }
