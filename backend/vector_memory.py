"""Tier 3 long-term memory as an embedded vector store: one JSONL file, no server, no new dependency.

add(text, scope, agents, source) stores a memory with its vector and metadata.
search(query, agent, scopes, k) returns the k most similar memories the agent is allowed to see.

Vectors come from NVIDIA's embedding API when NVIDIA_API_KEY is set (VECTOR_EMBED_MODEL, default
nvidia/nv-embedqa-e5-v5). Without a key, or if the call fails, a local hashing embedding is used, so search
always works offline. The two kinds are never mixed: each record keeps the embedder it was made with.

Only the librarian writes here (consolidated lessons and deal artifacts), never raw chats.
"""
import hashlib
import json
import math
import os
import re
import threading
import time
from pathlib import Path

import httpx

PATH = Path(__file__).parent / "data" / "vectors" / "memories.jsonl"
API_URL = os.getenv("VECTOR_EMBED_URL", "https://integrate.api.nvidia.com/v1/embeddings")
MODEL = os.getenv("VECTOR_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
HASH_DIM = 256

_lock = threading.Lock()


def _hash_embed(text: str) -> list[float]:
    """Bag of words and word pairs hashed into HASH_DIM buckets, L2-normalised. Offline and deterministic."""
    words = re.findall(r"[a-z0-9$]+", text.lower())
    vec = [0.0] * HASH_DIM
    for tok in words + [f"{a} {b}" for a, b in zip(words, words[1:])]:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % HASH_DIM] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _api_embed(text: str, input_type: str) -> list[float] | None:
    key = os.getenv("NVIDIA_API_KEY", "")
    if not key:
        return None
    try:
        r = httpx.post(API_URL, timeout=15, headers={"Authorization": f"Bearer {key}"},
                       json={"model": MODEL, "input": [text], "input_type": input_type, "encoding_format": "float"})
        r.raise_for_status()
        vec = r.json()["data"][0]["embedding"]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
    except Exception:
        return None


def embed(text: str, input_type: str = "passage") -> tuple[list[float], str]:
    vec = _api_embed(text, input_type)
    return (vec, MODEL) if vec else (_hash_embed(text), "hash256")


def _load() -> list[dict]:
    if not PATH.exists():
        return []
    out = []
    for line in PATH.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def add(text: str, scope: str, agents: list[str] | None = None, source: str = "") -> bool:
    """Store one memory. Same text in the same scope is stored once. agents=None means every agent."""
    with _lock:
        rows = _load()
        if any(r["text"] == text and r["scope"] == scope for r in rows):
            return False
        vec, embedder = embed(text)
        rec = {"text": text, "scope": scope, "agents": sorted(agents) if agents else ["all"], "source": source,
               "ts": time.time(), "embedder": embedder, "vector": [round(v, 5) for v in vec]}
        PATH.parent.mkdir(parents=True, exist_ok=True)
        with PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return True


def search(query: str, agent: str, scopes: list[str] | None = None, k: int = 3, min_score: float = 0.15) -> list[dict]:
    """Top k memories by cosine similarity, filtered by scope and by which agents may see them."""
    rows = [r for r in _load()
            if (not scopes or r["scope"] in scopes) and ("all" in r["agents"] or agent in r["agents"])]
    if not rows:
        return []
    cache: dict[str, list[float]] = {}
    scored = []
    for r in rows:
        if r["embedder"] not in cache:  # query embedded once per embedder, so vectors are never mixed
            cache[r["embedder"]] = _hash_embed(query) if r["embedder"] == "hash256" else (_api_embed(query, "query") or [])
        q = cache[r["embedder"]]
        if len(q) != len(r["vector"]):
            continue
        score = sum(a * b for a, b in zip(q, r["vector"]))
        if score >= min_score:
            scored.append((score, r))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [{"text": r["text"], "scope": r["scope"], "score": round(s, 3), "source": r["source"]} for s, r in scored[:k]]


def stats() -> dict:
    rows = _load()
    return {"memories": len(rows), "kb": round(PATH.stat().st_size / 1024, 1) if PATH.exists() else 0,
            "embedders": sorted({r["embedder"] for r in rows})}
