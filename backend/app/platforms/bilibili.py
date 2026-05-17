"""Zero-cookie Bilibili extractor (stdlib + public WBI APIs).

Flow (mirrors our Douyin approach — no user-supplied cookie files):
  1) Resolve BV/av URL → bvid + cid via ``x/web-interface/view``
  2) Sign with WBI keys from ``x/web-interface/nav``
  3) Fetch DASH playurl with ``try_look=1`` (guest-accessible streams)
  4) Expose format ladder; download merges video+audio via ffmpeg

Note: Many videos only expose 480p to guests; 720p/1080p may require a
logged-in session on Bilibili's side. We still surface the best guest rung.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from ..mp4_compat import vcodec_family

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
_API_HEADERS = {"User-Agent": DESKTOP_UA, "Referer": REFERER}

_BILI_HOST_RE = re.compile(
    r"^https?://(?:www\.)?bilibili\.com\b", re.IGNORECASE
)
_B23_RE = re.compile(r"^https?://(?:www\.)?b23\.tv/", re.IGNORECASE)
_BVID_RE = re.compile(r"([aAbB][vV]1\w+)", re.IGNORECASE)
_AV_RE = re.compile(r"/video/(?:av)(?P<aid>\d+)", re.IGNORECASE)
_FORMAT_ID_RE = re.compile(r"-(\d+)\.m4s\?")

# WBI mixin table (from Bilibili web player vendor JS, same as yt-dlp).
_WBI_MIXIN = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

_wbi_cache: Dict[str, Any] = {"ts": 0.0, "key": ""}
_WBI_TTL = 30.0

# Bilibili quality id → common label
_QN_HEIGHT = {
    127: 4320,
    126: 2160,
    125: 2160,
    120: 2160,
    116: 1080,
    112: 1080,
    80: 1080,
    64: 720,
    32: 480,
    16: 360,
}


def is_bilibili_url(url: str) -> bool:
    if not url:
        return False
    s = url.strip()
    return bool(_BILI_HOST_RE.search(s) or _B23_RE.search(s))


def _http_json(
    url: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    timeout: float = 12.0,
    require_ok: bool = True,
) -> Dict[str, Any]:
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers=_API_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    if require_ok and payload.get("code") not in (0, None):
        msg = payload.get("message") or payload.get("msg") or str(payload)
        code = payload.get("code")
        if code == -404 or "啥都木有" in str(msg):
            raise ValueError(
                "视频不存在或链接无效。请从浏览器地址栏原样复制 BV 号（大小写敏感），"
                f"勿手动改写字母。平台返回：{msg}"
            )
        raise ValueError(f"B 站接口错误：{msg}")
    return payload


def _follow_shortlink(url: str) -> str:
    if not _B23_RE.search(url):
        return url
    req = urllib.request.Request(url, headers=_API_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.geturl() or url
    except urllib.error.URLError:
        return url


def _normalize_bvid(raw: str) -> str:
    """BV ids are case-sensitive; only normalize the ``BV`` prefix itself."""
    if not raw or len(raw) < 3:
        return raw
    return "BV" + raw[2:]


def _extract_bvid(url: str) -> str:
    s = _follow_shortlink(url.strip())
    m = _BVID_RE.search(s)
    if m:
        return _normalize_bvid(m.group(1))
    m = _AV_RE.search(s)
    if m:
        data = _http_json(
            "https://api.bilibili.com/x/web-interface/view",
            query={"aid": m.group("aid")},
        )
        bvid = (data.get("data") or {}).get("bvid")
        if bvid:
            return _normalize_bvid(bvid)
    raise ValueError(
        "无法识别 B 站视频 ID，请粘贴视频页链接（如 https://www.bilibili.com/video/BVxxxx）。"
    )


def _page_index(url: str) -> int:
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query or "")
    raw = (qs.get("p") or ["1"])[-1]
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _wbi_key() -> str:
    now = time.time()
    if _wbi_cache.get("key") and now < float(_wbi_cache["ts"]) + _WBI_TTL:
        return str(_wbi_cache["key"])
    # Nav returns code -101 for guests but still ships wbi_img keys.
    data = _http_json(
        "https://api.bilibili.com/x/web-interface/nav",
        require_ok=False,
    )
    img = (data.get("data") or {}).get("wbi_img") or {}
    if not img.get("img_url"):
        raise ValueError("无法获取 B 站 WBI 签名密钥，请稍后再试。")
    parts = []
    for field in ("img_url", "sub_url"):
        raw = img.get(field) or ""
        parts.append(raw.rpartition("/")[2].partition(".")[0])
    lookup = "".join(parts)
    key = "".join(lookup[i] for i in _WBI_MIXIN)[:32]
    _wbi_cache.update(key=key, ts=now)
    return key


def _sign_wbi(params: Dict[str, Any]) -> Dict[str, Any]:
    signed = dict(params)
    signed["wts"] = round(time.time())
    cleaned = {
        k: "".join(c for c in str(v) if c not in "!'()*")
        for k, v in sorted(signed.items())
    }
    query = urllib.parse.urlencode(cleaned)
    cleaned["w_rid"] = hashlib.md5(f"{query}{_wbi_key()}".encode()).hexdigest()
    return cleaned


def _playinfo(
    bvid: str,
    cid: int,
    *,
    qn: Optional[int] = None,
    fnval: int = 16,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "bvid": bvid,
        "cid": int(cid),
        "fnval": fnval,  # 16 → DASH incl. H.264; 4048 → often AV1-only for guests
        "try_look": 1,  # guest-accessible preview streams
    }
    if qn is not None:
        params["qn"] = int(qn)
    signed = _sign_wbi(params)
    data = _http_json(
        "https://api.bilibili.com/x/player/wbi/playurl",
        query=signed,
    )
    return data.get("data") or {}


def _format_id_from_url(url: str, fallback: str) -> str:
    m = _FORMAT_ID_RE.search(url or "")
    return m.group(1) if m else fallback


def _pick_best_audio(audios: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not audios:
        return None
    return max(audios, key=lambda a: int(a.get("bandwidth") or 0))


def _video_height(video: Dict[str, Any]) -> Optional[int]:
    h = video.get("height")
    if h:
        return int(h)
    qn = video.get("id")
    if qn is not None:
        return _QN_HEIGHT.get(int(qn))
    return None


def _build_formats_from_playinfo(play_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn Bilibili DASH JSON into our internal format entries."""
    dash = play_info.get("dash") or {}
    videos = list(dash.get("video") or [])
    audios = list(dash.get("audio") or [])
    # Dolby / flac sidecars
    for extra in traverse_dolby(dash):
        audios.append(extra)

    if not videos and play_info.get("durl"):
        # Legacy progressive FLV — single file, no merge needed.
        seg = play_info["durl"][0]
        url = seg.get("url") or ""
        qn = int(play_info.get("quality") or 32)
        height = _QN_HEIGHT.get(qn, 480)
        return [
            _format_entry(
                f"flv-{qn}",
                height=height,
                direct_url=url,
                vcodec="h264",
                acodec="aac",
                muxed=True,
                filesize=seg.get("size"),
                tbr=float(seg.get("size") or 0) * 8 / max(seg.get("length") or 1, 1) / 1000,
                note=play_info.get("accept_description", [""])[0] if play_info.get("accept_description") else None,
            )
        ]

    best_audio = _pick_best_audio(audios)
    audio_url = (best_audio or {}).get("baseUrl") or (best_audio or {}).get("base_url")
    audio_id = str((best_audio or {}).get("id") or "audio")

    out: List[Dict[str, Any]] = []
    for v in videos:
        vurl = v.get("baseUrl") or v.get("base_url")
        if not vurl:
            continue
        fid = _format_id_from_url(vurl, str(v.get("id") or "0"))
        height = _video_height(v)
        vcodec = (v.get("codecs") or "avc1").split(".")[0]
        bw = int(v.get("bandwidth") or 0)
        out.append(
            _format_entry(
                fid,
                height=height,
                direct_url=vurl,
                video_url=vurl,
                audio_url=audio_url,
                audio_id=audio_id,
                vcodec=vcodec,
                acodec=None,
                muxed=False,
                filesize=v.get("size"),
                tbr=bw / 1000.0 if bw else None,
                width=v.get("width"),
            )
        )

    # Audio-only rung
    if best_audio and audio_url:
        abw = int(best_audio.get("bandwidth") or 0)
        out.append(
            _format_entry(
                audio_id,
                height=None,
                direct_url=audio_url,
                video_url=None,
                audio_url=audio_url,
                audio_id=audio_id,
                vcodec=None,
                acodec=(best_audio.get("codecs") or "mp4a").split(".")[0],
                muxed=False,
                is_audio_only=True,
                filesize=best_audio.get("size"),
                tbr=abw / 1000.0 if abw else None,
            )
        )

    return out


def traverse_dolby(dash: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    dolby = (dash.get("dolby") or {}).get("audio") or []
    out.extend(dolby)
    flac = (dash.get("flac") or {}).get("audio")
    if isinstance(flac, dict):
        out.append(flac)
    return out


def _format_entry(
    fid: str,
    *,
    height: Optional[int],
    direct_url: str,
    video_url: Optional[str] = None,
    audio_url: Optional[str] = None,
    audio_id: Optional[str] = None,
    vcodec: Optional[str] = "avc1",
    acodec: Optional[str] = None,
    muxed: bool = False,
    is_audio_only: bool = False,
    filesize: Optional[int] = None,
    tbr: Optional[float] = None,
    width: Optional[int] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "format_id": fid,
        "ext": "mp4",
        "resolution": f"{width}x{height}" if width and height else None,
        "height": height,
        "fps": None,
        "filesize": filesize,
        "tbr": tbr,
        "vcodec": vcodec,
        "acodec": acodec,
        "note": note,
        "is_audio_only": is_audio_only,
        "is_video_only": not is_audio_only and not muxed and acodec is None,
        "quicktime_friendly": (
            is_audio_only
            or muxed
            or vcodec_family(vcodec) == "h264"
        ),
        "_direct_url": direct_url,
        "_video_url": video_url,
        "_audio_url": audio_url,
        "_audio_id": audio_id,
        "_muxed": muxed,
        "_referer": REFERER,
    }


def _merge_playinfo_formats(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Merge video rungs from an additional qn-specific playinfo response."""
    merged = dict(base)
    dash_a = base.get("dash") or {}
    dash_b = extra.get("dash") or {}
    videos: Dict[str, Dict[str, Any]] = {}
    for v in (dash_a.get("video") or []) + (dash_b.get("video") or []):
        url = v.get("baseUrl") or v.get("base_url") or ""
        key = f"{v.get('id')}:{(v.get('codecs') or '')[:8]}:{_format_id_from_url(url, '')}"
        videos[key] = v
    audios = {a.get("id"): a for a in (dash_a.get("audio") or [])}
    for a in dash_b.get("audio") or []:
        audios[a.get("id")] = a
    merged["dash"] = {
        **dash_a,
        **dash_b,
        "video": list(videos.values()),
        "audio": list(audios.values()),
    }
    if not merged.get("accept_quality") and extra.get("accept_quality"):
        merged["accept_quality"] = extra["accept_quality"]
    if not merged.get("accept_description") and extra.get("accept_description"):
        merged["accept_description"] = extra["accept_description"]
    return merged


def _collect_playinfo(bvid: str, cid: int) -> Dict[str, Any]:
    play_info: Dict[str, Any] = {}
    for fnval in (16, 4048):
        try:
            chunk = _playinfo(bvid, cid, fnval=fnval)
            play_info = (
                _merge_playinfo_formats(play_info, chunk) if play_info else chunk
            )
        except (urllib.error.URLError, ValueError, json.JSONDecodeError):
            continue

    if not (play_info.get("dash") or play_info.get("durl")):
        raise ValueError("B 站未返回可下载流（视频可能需登录或为地区限制）。")

    parsed_qn = set()
    for v in (play_info.get("dash") or {}).get("video") or []:
        if v.get("id") is not None:
            parsed_qn.add(int(v["id"]))

    # Request missing guest qualities (same strategy as yt-dlp legacy path).
    for qn in play_info.get("accept_quality") or []:
        qn = int(qn)
        if qn in parsed_qn:
            continue
        for fnval in (16, 4048):
            try:
                extra = _playinfo(bvid, cid, qn=qn, fnval=fnval)
                play_info = _merge_playinfo_formats(play_info, extra)
                parsed_qn.add(qn)
                break
            except (urllib.error.URLError, ValueError, json.JSONDecodeError):
                continue

    return play_info


def _height_bucket(height: Optional[int]) -> int:
    """Treat 476p / 480p as the same rung for deduplication."""
    if not height:
        return 0
    h = int(height)
    for std in (2160, 1440, 1080, 720, 480, 360):
        if abs(h - std) <= 24:
            return std
    return h


def _dedupe_formats(formats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer H.264 per height when multiple codecs exist."""
    by_height: Dict[int, Dict[str, Any]] = {}
    audio: List[Dict[str, Any]] = []
    muxed: List[Dict[str, Any]] = []
    for f in formats:
        if f.get("_muxed"):
            muxed.append(f)
            continue
        if f.get("is_audio_only"):
            audio.append(f)
            continue
        h = _height_bucket(f.get("height"))
        prev = by_height.get(h)
        if not prev or vcodec_family(f.get("vcodec")) == "h264" and vcodec_family(
            prev.get("vcodec")
        ) != "h264":
            by_height[h] = f
        elif prev and vcodec_family(f.get("vcodec")) == vcodec_family(prev.get("vcodec")):
            if (f.get("tbr") or 0) > (prev.get("tbr") or 0):
                by_height[h] = f
    out = muxed + sorted(by_height.values(), key=lambda x: -(x.get("height") or 0))
    if audio:
        best = max(audio, key=lambda x: x.get("tbr") or 0)
        out.append(best)
    return out


def fetch(url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return ``(meta, formats)`` for a Bilibili watch URL."""
    bvid = _extract_bvid(url)
    page = _page_index(url)

    view = _http_json(
        "https://api.bilibili.com/x/web-interface/view",
        query={"bvid": bvid},
    )["data"]

    title = (view.get("title") or "").strip() or bvid
    pages = view.get("pages") or []
    if page > 1 and len(pages) >= page:
        part = pages[page - 1]
        cid = int(part["cid"])
        part_title = (part.get("part") or "").strip()
        if part_title:
            title = f"{title} p{page:02d} {part_title}"
    else:
        cid = int(view.get("cid") or pages[0]["cid"])

    play_info = _collect_playinfo(bvid, cid)
    formats = _dedupe_formats(_build_formats_from_playinfo(play_info))
    if not formats:
        raise ValueError("未能从 B 站解析到可下载格式。")

    meta: Dict[str, Any] = {
        "id": bvid,
        "title": title,
        "thumbnail": view.get("pic"),
        "duration": float(view.get("duration") or 0) or None,
        "uploader": (view.get("owner") or {}).get("name"),
        "extractor": "Bilibili",
        "webpage_url": f"https://www.bilibili.com/video/{bvid}"
        + (f"?p={page}" if page > 1 else ""),
        "view_count": (view.get("stat") or {}).get("view"),
    }
    return meta, formats


def resolve_download_target(
    formats: List[Dict[str, Any]], format_id: Optional[str], audio_only: bool
) -> Dict[str, Any]:
    """Pick the format row used by the downloader."""
    if audio_only:
        candidates = [f for f in formats if f.get("is_audio_only")]
        if not candidates:
            raise ValueError("该视频没有独立音频流。")
        return candidates[0]

    if format_id:
        chosen = next((f for f in formats if f["format_id"] == format_id), None)
        if chosen and not chosen.get("is_audio_only"):
            return chosen

    # Default: highest video height
    videos = [f for f in formats if not f.get("is_audio_only")]
    if not videos:
        raise ValueError("没有可下载的视频流。")
    return max(videos, key=lambda f: f.get("height") or 0)
