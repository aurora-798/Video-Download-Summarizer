"""Subtitle fetching layer for the AI summarizer.

We *prefer* platform-provided subtitles whenever they exist — that's
free, instant, and 100% accurate compared with ASR. yt-dlp exposes:

  info["subtitles"]            # human-authored (high quality)
  info["automatic_captions"]   # YouTube auto-generated (good enough)

For each language a list of variants `[{"ext": "vtt", "url": "..."}]`
is returned. We download the first VTT/JSON3 variant and parse it into
a uniform list of ``[{start, end, text}]`` cues.

Empirical coverage (tested on the live web):
- YouTube: ✅ both manual and auto captions, multi-language translation
- TED, Vimeo, etc. (whatever yt-dlp's extractor exposes)
- B 站  : ❌ guest API doesn't return subtitle_url (requires login)
- 抖音  : ❌ no subtitle track at all (video data simply lacks it)

So this module returns ``None`` for B 站/抖音 and the caller falls back
to ASR via ``transcriber.py``.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from yt_dlp import YoutubeDL

from .platforms import bilibili, douyin

logger = logging.getLogger("summarizer.subtitle")

# Ordered language priority. Anything not in this list is still acceptable
# (we fall back to "first available"), this is just for picking the best
# track when several are returned at once.
_LANG_PRIORITY = (
    "zh-Hans",
    "zh-CN",
    "zh-Hans-CN",
    "zh",
    "zh-Hant",
    "zh-TW",
    "en",
    "en-US",
    "en-GB",
)

# Subtitle formats we know how to parse, ordered by parser quality.
_EXT_PRIORITY = ("vtt", "srv3", "json3", "srt", "ttml")

_DEFAULT_TIMEOUT = 15.0

_VTT_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]+>")


class SubtitleCue:
    __slots__ = ("start", "end", "text")

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text

    def as_dict(self) -> Dict[str, Any]:
        return {"start": round(self.start, 2), "end": round(self.end, 2), "text": self.text}


# ----- public API ---------------------------------------------------------


def fetch_subtitle(url: str) -> Optional[Dict[str, Any]]:
    """Try to obtain platform-native subtitles for ``url``.

    Returns ``None`` when no subtitle is available (caller should fall
    back to ASR). On success returns::

        {
            "language": "zh-Hans",     # selected track language
            "source":   "manual",      # "manual" or "auto"
            "cues":     [SubtitleCue.as_dict(), ...],
            "text":     "joined plain text without timestamps",
        }
    """
    if not url:
        return None

    # B 站 / 抖音 — known dead ends, skip yt-dlp probing to save 1-2s.
    if bilibili.is_bilibili_url(url):
        logger.info("Skipping subtitle probe for Bilibili (guest API blocks it)")
        return None
    if douyin.is_douyin_url(url):
        logger.info("Skipping subtitle probe for Douyin (no subtitle track exists)")
        return None

    try:
        tracks = _list_tracks_via_ytdlp(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("yt-dlp subtitle probe failed for %s: %s", url, exc)
        return None

    chosen = _pick_best_track(tracks)
    if not chosen:
        return None

    lang, source, variants = chosen
    cues = _download_and_parse(variants)
    if not cues:
        return None

    text = "\n".join(c.text for c in cues if c.text.strip())
    return {
        "language": lang,
        "source": source,
        "cues": [c.as_dict() for c in cues],
        "text": text,
    }


# ----- yt-dlp probing -----------------------------------------------------


def _list_tracks_via_ytdlp(url: str) -> Dict[str, List[Tuple[str, str, List[Dict[str, Any]]]]]:
    """Run yt-dlp in metadata-only mode and group tracks by source.

    Returns ``{"manual": [(lang, "manual", variants), ...], "auto": [...]}``.
    Each ``variants`` entry is a list of ``{"ext", "url"}`` dicts (raw from
    yt-dlp), which we keep so we can pick the best parseable format.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": list(_LANG_PRIORITY) + ["en.*", "zh.*"],
        # Don't actually write to disk — we just want the listing.
        "outtmpl": "/dev/null",
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    out: Dict[str, List[Tuple[str, str, List[Dict[str, Any]]]]] = {
        "manual": [(lang, "manual", variants) for lang, variants in manual.items() if variants],
        "auto": [(lang, "auto", variants) for lang, variants in auto.items() if variants],
    }
    return out


def _pick_best_track(
    tracks: Dict[str, List[Tuple[str, str, List[Dict[str, Any]]]]],
) -> Optional[Tuple[str, str, List[Dict[str, Any]]]]:
    """Prefer manual over auto; within each, prefer our language order."""

    def _lang_rank(lang: str) -> int:
        for i, pref in enumerate(_LANG_PRIORITY):
            if lang.lower() == pref.lower() or lang.lower().startswith(pref.lower() + "-"):
                return i
        return len(_LANG_PRIORITY) + 1

    for source_key in ("manual", "auto"):
        items = tracks.get(source_key) or []
        if not items:
            continue
        items.sort(key=lambda t: _lang_rank(t[0]))
        # Filter out tracks whose variants are all unsupported extensions.
        for lang, source, variants in items:
            if any(v.get("ext", "").lower() in _EXT_PRIORITY for v in variants):
                return lang, source, variants
    return None


# ----- format-specific parsers -------------------------------------------


def _download_and_parse(variants: List[Dict[str, Any]]) -> List[SubtitleCue]:
    """Download the highest-priority variant we can parse."""
    ordered = sorted(
        variants,
        key=lambda v: _EXT_PRIORITY.index(v.get("ext", "").lower())
        if v.get("ext", "").lower() in _EXT_PRIORITY
        else 999,
    )
    for v in ordered:
        ext = (v.get("ext") or "").lower()
        url = v.get("url")
        if not url or ext not in _EXT_PRIORITY:
            continue
        try:
            raw = _http_get(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("subtitle download failed (%s): %s", ext, exc)
            continue
        try:
            if ext == "vtt":
                return _parse_vtt(raw)
            if ext == "srt":
                return _parse_srt(raw)
            if ext == "json3":
                return _parse_json3(raw)
            if ext == "srv3":
                return _parse_srv3(raw)
            if ext == "ttml":
                return _parse_ttml(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("subtitle parse failed (%s): %s", ext, exc)
            continue
    return []


def _http_get(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
        data = resp.read()
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))


def _parse_vtt(raw: str) -> List[SubtitleCue]:
    cues: List[SubtitleCue] = []
    blocks = re.split(r"\r?\n\r?\n", raw.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # Header or NOTE block — skip.
        if lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue
        time_line_idx = 0
        # Optional cue ID line before timing.
        if "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            time_line_idx = 1
        if time_line_idx >= len(lines):
            continue
        m = _VTT_TIME_RE.search(lines[time_line_idx])
        if not m:
            continue
        start = _ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        text_lines = lines[time_line_idx + 1 :]
        text = "\n".join(_VTT_TAG_RE.sub("", ln) for ln in text_lines).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return _dedupe_consecutive(cues)


def _parse_srt(raw: str) -> List[SubtitleCue]:
    cues: List[SubtitleCue] = []
    for block in re.split(r"\r?\n\r?\n", raw.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        time_line = lines[1] if lines[0].strip().isdigit() else lines[0]
        text_start = 2 if lines[0].strip().isdigit() else 1
        m = _VTT_TIME_RE.search(time_line)
        if not m:
            continue
        start = _ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        text = "\n".join(lines[text_start:]).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return _dedupe_consecutive(cues)


def _parse_json3(raw: str) -> List[SubtitleCue]:
    """YouTube's preferred internal format. Events have ``tStartMs`` +
    ``dDurationMs`` and segments contain ``utf8`` text fragments."""
    data = json.loads(raw)
    cues: List[SubtitleCue] = []
    for ev in data.get("events") or []:
        if "segs" not in ev or "tStartMs" not in ev:
            continue
        start = ev["tStartMs"] / 1000.0
        end = start + (ev.get("dDurationMs") or 0) / 1000.0
        text = "".join((seg.get("utf8") or "") for seg in ev["segs"]).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return _dedupe_consecutive(cues)


def _parse_srv3(raw: str) -> List[SubtitleCue]:
    """YouTube's XML-based caption format. <p t="..." d="..."> blocks."""
    import xml.etree.ElementTree as ET

    cues: List[SubtitleCue] = []
    root = ET.fromstring(raw)
    for p in root.iter("p"):
        t = p.get("t")
        d = p.get("d")
        if not t:
            continue
        start = int(t) / 1000.0
        end = start + (int(d) / 1000.0 if d else 0)
        # Text can be split across <s> child elements or be in p.text.
        text_parts = []
        if p.text:
            text_parts.append(p.text)
        for s in p:
            if s.text:
                text_parts.append(s.text)
            if s.tail:
                text_parts.append(s.tail)
        text = "".join(text_parts).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return _dedupe_consecutive(cues)


def _parse_ttml(raw: str) -> List[SubtitleCue]:
    import xml.etree.ElementTree as ET

    cues: List[SubtitleCue] = []
    root = ET.fromstring(raw)
    # TTML namespaces — use local-name match for resilience.
    for p in root.iter():
        if not p.tag.endswith("}p") and p.tag != "p":
            continue
        begin = p.get("begin")
        end_attr = p.get("end")
        if not begin or not end_attr:
            continue
        start = _ttml_time(begin)
        end = _ttml_time(end_attr)
        text = "".join(p.itertext()).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return _dedupe_consecutive(cues)


def _ttml_time(raw: str) -> float:
    """TTML time can be ``hh:mm:ss.ms`` or ``Ns`` (seconds)."""
    if raw.endswith("s") and ":" not in raw:
        try:
            return float(raw[:-1])
        except ValueError:
            return 0.0
    parts = raw.split(":")
    while len(parts) < 3:
        parts.insert(0, "0")
    h, m, s = parts[-3], parts[-2], parts[-1]
    sec, _, ms = s.partition(".")
    return int(h) * 3600 + int(m) * 60 + int(sec) + (int(ms) / (10 ** len(ms)) if ms else 0)


def _dedupe_consecutive(cues: List[SubtitleCue]) -> List[SubtitleCue]:
    """Auto-captions on YouTube often emit overlapping rolling text where
    each cue duplicates the previous one with one extra word appended.
    We collapse those into a single cue per "stable" line."""
    if not cues:
        return cues
    out: List[SubtitleCue] = []
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        if out and (out[-1].text.endswith(text) or text.startswith(out[-1].text)):
            # Newer cue is a strict extension — replace.
            if len(text) >= len(out[-1].text):
                out[-1] = SubtitleCue(out[-1].start, cue.end, text)
            continue
        out.append(cue)
    return out
