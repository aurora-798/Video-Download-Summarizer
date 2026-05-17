"""URL normalization for platforms whose share / app URLs aren't directly
consumable by yt-dlp.

We keep this layer dead simple and pure-string: we don't make HTTP calls to
resolve short links here (yt-dlp itself handles many redirects). We only
rewrite obvious cases that yt-dlp's extractors can't pattern-match.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


_DOUYIN_USER_MODAL_RE = re.compile(r"douyin\.com/user/[^?]+", re.IGNORECASE)
_DOUYIN_NOTE_RE = re.compile(r"douyin\.com/note/(\d+)", re.IGNORECASE)
_DOUYIN_DISCOVER_RE = re.compile(r"douyin\.com/discover.*[?&]modal_id=(\d+)", re.IGNORECASE)


def normalize_url(url: str) -> str:
    """Rewrite a few known-tricky URL shapes into yt-dlp-friendly ones.

    Currently handled:
      - Douyin "user collection / favorite" modal URLs:
          https://www.douyin.com/user/xxx?modal_id=7630...&showTab=favorite_collection
          -> https://www.douyin.com/video/7630...
      - Douyin /note/<id> URLs (older share format) -> /video/<id>
      - Douyin /discover?modal_id=<id> URLs -> /video/<id>

    Anything we don't recognize is returned unchanged.
    """
    if not url:
        return url
    s = url.strip()

    parsed = urlparse(s)
    host = (parsed.netloc or "").lower()
    qs = parse_qs(parsed.query or "")

    # 1) Douyin user/discover pages that wrap a real video in a modal_id query.
    if "douyin.com" in host:
        modal_ids = qs.get("modal_id") or []
        if modal_ids and (
            _DOUYIN_USER_MODAL_RE.search(s)
            or _DOUYIN_DISCOVER_RE.search(s)
            or parsed.path.startswith("/user/")
            or parsed.path.startswith("/discover")
        ):
            return f"https://www.douyin.com/video/{modal_ids[0]}"

        # /note/<id> -> /video/<id>
        m = _DOUYIN_NOTE_RE.search(s)
        if m:
            return f"https://www.douyin.com/video/{m.group(1)}"

    return s
