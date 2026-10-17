"""NVIDIA check: key works, speech and embedding functions exist, one real round trip each.

Run: cd backend && python nvidia_check.py

Get the key: https://build.nvidia.com > sign in > your profile > API Keys > Generate (starts with nvapi-).
Put it in backend/.env as NVIDIA_API_KEY=nvapi-... (never commit it).
Without the key the demo still runs: voice falls back to text and memory search uses the local embedding.
"""
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
import voice  # noqa: E402  (reads env at import)

NVCF_FUNCTIONS = "https://api.nvcf.nvidia.com/v2/nvcf/functions?visibility=public,authorized"
EMBED_URL = os.getenv("VECTOR_EMBED_URL", "https://integrate.api.nvidia.com/v1/embeddings")
EMBED_MODEL = os.getenv("VECTOR_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
PHRASE = "Hello, this is the dealer line. We buy used cars."


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def functions_list(key: str) -> list[dict]:
    r = httpx.get(NVCF_FUNCTIONS, headers={"Authorization": f"Bearer {key}"}, timeout=20)
    r.raise_for_status()
    return r.json().get("functions", [])


def main() -> int:
    key = os.getenv("NVIDIA_API_KEY", "")
    if not key:
        print("NVIDIA_API_KEY not set. Get one at https://build.nvidia.com (profile > API Keys) and add it to backend/.env.")
        return 1
    check("key present", True)

    # 1. Key works and speech functions are deployed to this account.
    try:
        fns = functions_list(key)
    except httpx.HTTPStatusError as e:
        check("NVCF functions list", False, f"HTTP {e.response.status_code}: check the key")
        return 1
    except Exception as e:
        check("NVCF functions list", False, f"{type(e).__name__}: {str(e)[:120]}")
        return 1
    active = {f.get("name", "").removeprefix("ai-"): f["id"] for f in fns if f.get("status") == "ACTIVE"}
    check("NVCF functions list", True, f"{len(active)} active functions")

    failed = 0
    for label, model in (("ASR (Parakeet)", voice.ASR_MODEL), ("TTS (Magpie)", voice.TTS_MODEL)):
        if model in active:
            check(f"{label} function", True, model)
        else:
            near = sorted(n for n in active if any(s in n.lower() for s in ("parakeet", "magpie", "tts", "asr")))
            check(f"{label} function", False, f"'{model}' not active. Set NVIDIA_ASR_MODEL / NVIDIA_TTS_MODEL to one of: {', '.join(near) or 'none'}")
            failed += 1

    # 2. TTS -> ASR round trip: speak a phrase, transcribe it back. Checks voice name, both functions, audio format.
    if not failed:
        try:
            voice._function_ids.clear()
            t0 = time.monotonic()
            pcm = voice.speak(PHRASE, sample_rate_hz=16000)
            if pcm is None:
                raise RuntimeError("speak() returned nothing: check NVIDIA_TTS_VOICE (model.locale.speaker, e.g. Magpie-Multilingual.EN-US.Aria)")
            wav = voice.to_wav(pcm, 16000)
            ok = check("TTS speak", True, f"{len(pcm) // 32000:.1f}s of audio in {time.monotonic() - t0:.1f}s")
            heard = voice.transcribe(wav)
            if heard is None:
                raise RuntimeError("transcribe() returned nothing: check NVIDIA_ASR_MODEL and the WAV format")
            words = {w.strip(".,!?").lower() for w in heard.split()}
            ok = check("ASR round trip", bool(words & {"dealer", "cars", "used", "hello"}), f"heard: {heard!r}") and ok
            failed += not ok
        except Exception as e:
            check("speech round trip", False, f"{type(e).__name__}: {str(e)[:200]}")
            failed += 1

    # 3. Embeddings for long-term memory search.
    try:
        r = httpx.post(EMBED_URL, headers={"Authorization": f"Bearer {key}"}, timeout=20,
                       json={"model": EMBED_MODEL, "input": ["used Toyota RAV4 deal"], "input_type": "query", "encoding_format": "float"})
        vec = r.json()["data"][0]["embedding"] if r.status_code == 200 else None
        ok = check("embeddings", bool(vec), f"{EMBED_MODEL}, dim {len(vec)}" if vec else f"HTTP {r.status_code} {r.text[:120]}")
        failed += not ok
    except Exception as e:
        check("embeddings", False, f"{type(e).__name__}: {str(e)[:120]}")
        failed += 1

    print("\nAll NVIDIA pieces ready." if not failed else f"\n{failed} piece(s) not ready. The demo still runs on text and local search.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
