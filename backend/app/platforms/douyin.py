"""Zero-cookie, zero-ffmpeg Douyin extractor.

We hit `https://www.iesdouyin.com/share/video/<aweme_id>/` with a mobile
User-Agent. Douyin server-renders the share page and embeds the full video
JSON in a `_ROUTER_DATA = {...}` blob. From there we read the muxed mp4
URL directly — no signing, no cookies, no ffmpeg.

The whole module is stdlib-only so the user doesn't need extra pip installs.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 "
    "Mobile/15E148 Safari/604.1"
)

SHARE_TPL = "https://www.iesdouyin.com/share/video/{aweme_id}/"

# We accept every common Douyin URL shape and reduce them to an aweme_id:
#   https://www.douyin.com/video/<id>
#   https://www.douyin.com/note/<id>
#   https://www.douyin.com/discover?modal_id=<id>
#   https://www.douyin.com/user/<sec_uid>?modal_id=<id>
#   https://www.iesdouyin.com/share/video/<id>
#   https://v.douyin.com/<short>/        (mobile share short-link, needs HEAD redirect)
_VIDEO_ID_RE = re.compile(r"/(?:video|note|share/video)/(\d+)")
_DOUYIN_HOST_RE = re.compile(r"^https?://(?:www\.|m\.|v\.)?(?:iesdouyin|douyin|amemv)\.com\b", re.IGNORECASE)
_SHORTLINK_RE = re.compile(r"^https?://v\.douyin\.com/[\w-]+/?", re.IGNORECASE)


def is_douyin_url(url: str) -> bool:
    return bool(url and _DOUYIN_HOST_RE.search(url.strip()))


def _follow_shortlink(url: str, timeout: float = 8.0) -> str:
    """v.douyin.com/<token>/ short links are 302s pointing at the real page.
    We only need to read the Location header — no body — and most clients
    chase redirects automatically, so a regular GET works fine.
    """
    if not _SHORTLINK_RE.match(url):
        return url
    req = urllib.request.Request(url, headers={"User-Agent": MOBILE_UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.geturl() or url
    except urllib.error.URLError:
        return url


def extract_aweme_id(url: str) -> Optional[str]:
    """Pull the aweme_id from any of the Douyin URL shapes we know about."""
    if not url:
        return None
    s = url.strip()
    s = _follow_shortlink(s)

    parsed = urllib.parse.urlparse(s)
    qs = urllib.parse.parse_qs(parsed.query or "")

    modal_id = (qs.get("modal_id") or [None])[0]
    if modal_id and modal_id.isdigit():
        return modal_id

    m = _VIDEO_ID_RE.search(parsed.path or "")
    if m:
        return m.group(1)

    item_ids = (qs.get("item_ids") or qs.get("aweme_id") or [None])[0]
    if item_ids and item_ids.isdigit():
        return item_ids

    return None


def _fetch_share_html(aweme_id: str, timeout: float = 10.0) -> str:
    url = SHARE_TPL.format(aweme_id=aweme_id)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": MOBILE_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    encoding = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="replace")


def _parse_router_data(html: str) -> Dict[str, Any]:
    m = re.search(r"_ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        raise ValueError("分享页未包含 _ROUTER_DATA，抖音可能临时升级了反爬，请稍后再试。")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"_ROUTER_DATA JSON 解析失败：{e}") from e


def _find_item(router_data: Dict[str, Any]) -> Dict[str, Any]:
    """The page key is parameterized (`video_(id)/page`, `note_(id)/page`,
    etc.). We scan loaderData for the first child that carries an item_list."""
    loader = (router_data or {}).get("loaderData") or {}
    for _key, page in loader.items():
        if not isinstance(page, dict):
            continue
        items = (page.get("videoInfoRes") or {}).get("item_list") or []
        if items:
            return items[0]
    raise ValueError("分享页 JSON 内未找到视频条目（可能视频已删除或被限制）。")


def _no_watermark_url(raw_url: str) -> str:
    """`/aweme/v1/playwm/...` is the watermarked variant; swapping it for
    `/aweme/v1/play/...` gives the same file without the Douyin logo overlay.
    Both URLs follow the same redirect chain, so we can swap unconditionally.
    """
    return raw_url.replace("/aweme/v1/playwm/", "/aweme/v1/play/").replace(
        "/playwm/", "/play/"
    )


def _build_format_entry(
    fid: str,
    url: str,
    *,
    height: Optional[int] = None,
    width: Optional[int] = None,
    bitrate: Optional[int] = None,
    label: str = "",
) -> Dict[str, Any]:
    """Shape a single download option the way the rest of the app expects.

    Note: we deliberately leave `height=None` so the frontend's
    "1080p+ requires VIP" gate doesn't trigger. Douyin only exposes a
    single source quality, so there's no resolution ladder to gate on.
    """
    return {
        "format_id": fid,
        "ext": "mp4",
        "resolution": f"{width}x{height}" if width and height else None,
        "height": None,
        "fps": None,
        "filesize": None,
        "tbr": (bitrate / 1000.0) if bitrate else None,
        "vcodec": "h264",
        "acodec": "aac",
        "note": label or None,
        "is_audio_only": False,
        "is_video_only": False,
        # Custom keys our downloader reads back to fetch the real bytes:
        "_direct_url": url,
        "_referer": "https://www.douyin.com/",
    }


def fetch(url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return `(meta, formats)` for a Douyin URL.

    `meta` mirrors the shape of yt-dlp's info dict so downstream code that
    expects `title/thumbnail/uploader/...` keeps working.
    """
    aweme_id = extract_aweme_id(url)
    if not aweme_id:
        raise ValueError(
            "无法从链接中提取抖音视频 ID，请直接复制视频详情页链接（含 /video/ 数字 那段）。"
        )

    html = _fetch_share_html(aweme_id)
    router = _parse_router_data(html)
    item = _find_item(router)

    title = (item.get("desc") or "").strip() or f"抖音视频 {aweme_id}"
    author = (item.get("author") or {}).get("nickname")
    duration_ms = item.get("duration") or (item.get("video") or {}).get("duration") or 0
    duration = duration_ms / 1000.0 if duration_ms else None

    video = item.get("video") or {}
    play_addr = video.get("play_addr") or {}
    url_list = [u for u in (play_addr.get("url_list") or []) if u]
    if not url_list:
        raise ValueError("抖音返回的视频地址为空（可能内容已被作者删除或仅好友可见）。")

    width = video.get("width")
    height = video.get("height")
    # The "playwm" URL works as-is, but we prefer the no-watermark variant
    # and fall back if the cleaner URL doesn't redirect.
    primary = _no_watermark_url(url_list[0])
    fallback = url_list[0]

    cover_urls = (video.get("cover") or {}).get("url_list") or []
    thumbnail = cover_urls[0] if cover_urls else None

    statistics = item.get("statistics") or {}
    view_count = statistics.get("play_count")

    formats = [
        _build_format_entry(
            "douyin-nwm", primary, height=height, width=width, label="无水印 · 原画质"
        ),
        _build_format_entry(
            "douyin-wm", fallback, height=height, width=width, label="带水印 · 原画质（兜底）"
        ),
    ]

    meta: Dict[str, Any] = {
        "id": aweme_id,
        "title": title,
        "thumbnail": thumbnail,
        "duration": duration,
        "uploader": author,
        "extractor": "Douyin",
        "webpage_url": f"https://www.douyin.com/video/{aweme_id}",
        "view_count": view_count,
    }
    return meta, formats
