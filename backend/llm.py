"""Crusoe Managed Inference client (OpenAI-compatible) with Nemotron tiers. Falls back to a mock when no key is set.

Tiers (limits are per model, so roles are spread across models on purpose):
  smart  - Owner / Buyer / Seller leads, seller + buyer talk, KBB appraisal  (Nemotron 3 Super)
  fast   - listing extraction, classification                                 (Nemotron 3 Nano)
  sim    - simulated sellers/buyers, librarian, mistake summaries             (Nemotron 3.5 Lightning)
  vision - listing photo checks                                               (Nemotron 3 Nano Omni)
"""
import asyncio
import json
import os
import random
import re
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

BASE_URL = os.getenv("CRUSOE_BASE_URL", "https://api.inference.crusoecloud.com/v1")
TIERS = {
    "smart": os.getenv("CRUSOE_MODEL_SMART", "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B"),
    "fast": os.getenv("CRUSOE_MODEL_FAST", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
    "sim": os.getenv("CRUSOE_MODEL_SIM", "nvidia/Nemotron-3.5-Lightning-30B-A3B"),
    "vision": os.getenv("CRUSOE_MODEL_VISION", "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"),
}
RPM = int(os.getenv("CRUSOE_RPM", "30"))  # per model: 30 without a payment method, 600 with one
MAX_TRIES = 4

_key = os.getenv("CRUSOE_API_KEY", "")
_client = AsyncOpenAI(base_url=BASE_URL, api_key=_key, timeout=90) if _key else None

_calls: dict[str, list[float]] = {}  # model -> request timestamps in the last 60s
_locks: dict[str, asyncio.Lock] = {}
_no_template_kwargs: set[str] = set()  # models that rejected chat_template_kwargs
STATS: dict[str, dict] = {}  # model -> {calls, errors, latency_total, last_latency}
DEGRADE_AFTER = 2  # consecutive failed calls before switching to mock text
DEGRADE_SECS = float(os.getenv("LLM_DEGRADE_SECS", "60"))
_fails = 0
_degraded_until = 0.0


def degraded() -> bool:
    return time.monotonic() < _degraded_until


def live() -> bool:
    """Real model text is available: a key is set and Crusoe isn't in a failure cooldown."""
    return _client is not None and not degraded()


def _failed() -> None:
    global _fails, _degraded_until
    _fails += 1
    if _fails >= DEGRADE_AFTER:
        _degraded_until = time.monotonic() + DEGRADE_SECS
        _fails = 0


async def _throttle(model: str) -> None:
    """Client-side RPM limiter so a swarm burst waits instead of eating 429s."""
    async with _locks.setdefault(model, asyncio.Lock()):
        now = time.monotonic()
        recent = [t for t in _calls.get(model, []) if now - t < 60]
        if len(recent) >= RPM:
            await asyncio.sleep(60 - (now - recent[0]) + 0.05)
            now = time.monotonic()
            recent = [t for t in recent if now - t < 60]
        _calls[model] = recent + [now]


def _record(model: str, latency: float | None) -> None:
    s = STATS.setdefault(model, {"calls": 0, "errors": 0, "latency_total": 0.0, "last_latency": 0.0})
    if latency is None:
        s["errors"] += 1
    else:
        s["calls"] += 1
        s["latency_total"] += latency
        s["last_latency"] = round(latency, 2)


def stats() -> dict:
    """Per-model call counts and latency for the dashboard footer."""
    out = {}
    for tier, model in TIERS.items():
        s = STATS.get(model, {})
        avg = round(s["latency_total"] / s["calls"], 2) if s.get("calls") else None
        out[tier] = {"model": model, **s, "avg_latency": avg}
    return out


async def chat(
    system: str,
    user: str,
    temperature: float = 0.2,
    tier: str = "smart",
    think: bool = False,
    max_tokens: int | None = None,
    images: list[str] | None = None,
) -> str:
    global _fails
    if not live():
        return _mock(system, user)
    try:
        out = await _call(system, user, temperature, tier, think, max_tokens, images)
    except Exception:
        _failed()
        raise
    _fails = 0
    return out


async def _call(system, user, temperature, tier, think, max_tokens, images) -> str:
    model = TIERS[tier]
    content = [{"type": "text", "text": user}] + [
        {"type": "image_url", "image_url": {"url": u}} for u in images or []
    ] if images else user
    kwargs = {
        "model": model,
        "temperature": temperature,
        # reasoning tokens count against max_tokens; too small = empty content
        "max_tokens": max_tokens or (4096 if think else 1024),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
    }
    if model not in _no_template_kwargs:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": think}}

    for attempt in range(MAX_TRIES):
        await _throttle(model)
        t0 = time.monotonic()
        try:
            r = await _client.chat.completions.create(**kwargs)
            _record(model, time.monotonic() - t0)
            msg = r.choices[0].message
            out = msg.content or ""
            if not out and r.choices[0].finish_reason == "length":
                extra = msg.model_dump()
                out = extra.get("reasoning_content") or extra.get("reasoning") or ""
            return out
        except APIStatusError as e:
            _record(model, None)
            if e.status_code == 400 and "extra_body" in kwargs:
                _no_template_kwargs.add(model)  # model does not take the thinking toggle
                kwargs.pop("extra_body")
                continue
            if e.status_code not in (429, 500, 502, 503) or attempt == MAX_TRIES - 1:
                raise
            wait = float(e.response.headers.get("retry-after") or min(20, 2 ** attempt))
        except (APIConnectionError, APITimeoutError):
            _record(model, None)
            if attempt == MAX_TRIES - 1:
                raise
            wait = min(20, 2 ** attempt)
        await asyncio.sleep(wait + random.random())
    return ""


async def chat_json(system: str, user: str, tier: str = "smart", think: bool = False) -> dict | list:
    """JSON reply or {} - never raises, so one bad call can't kill the swarm."""
    for _ in range(2):
        try:
            raw = await chat(system + "\nReply with valid JSON only.", user, temperature=0, tier=tier, think=think)
            m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def _mock(system: str, user: str) -> str:
    """Offline demo-safe stub so the UI works without keys."""
    if "definition of done" in system:
        return '["Answer is non-empty", "Answer addresses the goal directly", "Answer is concrete, no vague claims"]'
    if "verifier" in system:
        return '{"results": [{"check": "mock", "pass": true, "reason": "mock mode"}]}'
    return "[mock] Set CRUSOE_API_KEY in .env for real output."
