"""Thin streaming client for OpenAI-compatible Chat Completions APIs.

Defaults are configured for DeepSeek (``deepseek-chat``) because that's
the one the project chose. The same code targets Moonshot Kimi, OpenAI,
Aliyun Qwen, SiliconFlow, etc. — just change ``OPENAI_BASE_URL``,
``OPENAI_MODEL`` and ``OPENAI_API_KEY`` in ``.env``.

Why httpx and not the official openai SDK:
- one less heavy dep (we only need streaming chat)
- we already need httpx for the audio-transcription backend
- gives us tight control over SSE parsing and timeouts
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterator, List, Optional

import httpx

logger = logging.getLogger("summarizer.llm")

_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"


class LLMConfigError(RuntimeError):
    """Raised when no API key / base URL is configured."""


def _config() -> Dict[str, str]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    model = (os.getenv("OPENAI_MODEL") or _DEFAULT_MODEL).strip()
    if not api_key:
        raise LLMConfigError(
            "未设置 OPENAI_API_KEY。请在 backend/.env 中配置：\n"
            "  OPENAI_API_KEY=sk-xxx\n"
            "  OPENAI_BASE_URL=https://api.deepseek.com  (默认)\n"
            "  OPENAI_MODEL=deepseek-chat                (默认)"
        )
    return {"api_key": api_key, "base_url": base_url, "model": model}


def stream_chat(
    messages: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: int = 4096,
    timeout: float = 300.0,
) -> Iterator[str]:
    """Stream Chat-Completions deltas. Yields text chunks as they arrive.

    Raises ``LLMConfigError`` if config is missing, or ``httpx.HTTPStatusError``
    on a non-2xx final response.
    """
    cfg = _config()
    url = f"{cfg['base_url']}/v1/chat/completions"
    payload: Dict[str, Any] = {
        "model": model or cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    logger.info("LLM streaming: model=%s base=%s", payload["model"], cfg["base_url"])
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=20.0)) as client:
        with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code >= 400:
                body = resp.read().decode("utf-8", errors="replace")
                raise httpx.HTTPStatusError(
                    f"LLM API {resp.status_code}: {body[:500]}",
                    request=resp.request,
                    response=resp,
                )
            for line in resp.iter_lines():
                if not line:
                    continue
                # SSE lines look like ``data: {...}`` or ``data: [DONE]``.
                if line.startswith("data:"):
                    raw = line[5:].strip()
                else:
                    raw = line.strip()
                if not raw or raw == "[DONE]":
                    if raw == "[DONE]":
                        break
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug("skip non-JSON SSE line: %r", raw[:120])
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0] or {}).get("delta") or {}
                # Some endpoints (Moonshot) put text in 'content', others
                # occasionally use 'reasoning_content' — we accept both.
                piece = delta.get("content")
                if piece:
                    yield piece


def describe_config() -> Dict[str, Any]:
    """For /api/health style introspection. Hides the api_key."""
    base_url = (os.getenv("OPENAI_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    model = (os.getenv("OPENAI_MODEL") or _DEFAULT_MODEL).strip()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return {
        "configured": bool(api_key),
        "base_url": base_url,
        "model": model,
    }
