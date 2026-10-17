"""Quick Crusoe check: key works, tier models exist, one tiny call per tier. Run: cd backend && python crusoe_check.py"""
import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
import llm  # noqa: E402  (reads env at import)


async def main() -> int:
    key = os.getenv("CRUSOE_API_KEY", "")
    if not key:
        print("CRUSOE_API_KEY not set. Create an Intelligence API key: Crusoe Console > Intelligence Foundry > API Keys.")
        print("(CRUSOE_ACCESS_KEY / CRUSOE_SECRET_KEY are cloud keys and do not work for inference.)")
        return 1
    r = httpx.get(f"{llm.BASE_URL}/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
    if r.status_code != 200:
        print(f"GET /models -> {r.status_code}. Check key, project, expiry, and CRUSOE_BASE_URL={llm.BASE_URL}")
        return 1
    models = {m["id"]: m for m in r.json().get("data", [])}
    print(f"key ok, {len(models)} models. RPM per model assumed: {llm.RPM}")
    nemotron = sorted(m for m in models if "nemotron" in m.lower())
    print("nemotron on this project:", ", ".join(nemotron) or "none")

    failed = 0
    for tier, model in llm.TIERS.items():
        m = models.get(model)
        if not m:
            near = [x for x in models if x.lower() == model.lower()]
            print(f"[{tier}] MISSING {model}" + (f" (case differs: {near[0]})" if near else ""))
            failed += 1
            continue
        t0 = time.monotonic()
        try:
            out = await llm.chat("Reply with one word.", "Say OK.", tier=tier, max_tokens=256)
            ok = bool(out.strip())
            print(f"[{tier}] {model} {time.monotonic() - t0:.1f}s {'OK' if ok else 'EMPTY'} tags={m.get('tags')}")
            failed += not ok
        except Exception as e:
            print(f"[{tier}] {model} ERROR {type(e).__name__}: {str(e)[:160]}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
