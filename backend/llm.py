"""Thin Crusoe Managed Inference client (OpenAI-compatible). Falls back to a mock when no key is set."""
import json
import os
import re

from openai import AsyncOpenAI

MODEL = os.getenv("CRUSOE_MODEL", "nvidia/nemotron-3-super-120b-a12b")
_key = os.getenv("CRUSOE_API_KEY", "")
_client = (
    AsyncOpenAI(base_url=os.getenv("CRUSOE_BASE_URL", "https://api.crusoe.ai/v1"), api_key=_key)
    if _key
    else None
)


async def chat(system: str, user: str, temperature: float = 0.2) -> str:
    if _client is None:
        return _mock(system, user)
    r = await _client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return r.choices[0].message.content or ""


async def chat_json(system: str, user: str) -> dict | list:
    raw = await chat(system + "\nReply with valid JSON only.", user, temperature=0)
    m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)
    return json.loads(m.group(1)) if m else {}


def _mock(system: str, user: str) -> str:
    """Offline demo-safe stub so the UI works without keys."""
    if "definition of done" in system:
        return '["Answer is non-empty", "Answer addresses the goal directly", "Answer is concrete, no vague claims"]'
    if "verifier" in system:
        return '{"results": [{"check": "mock", "pass": true, "reason": "mock mode"}]}'
    return "[mock] Set CRUSOE_API_KEY in .env for real output."
