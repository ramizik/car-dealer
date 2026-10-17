from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import html  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import brain  # noqa: E402
import llm  # noqa: E402
import dealer_memory  # noqa: E402
import dealer_profile  # noqa: E402
import loop  # noqa: E402
import swarm  # noqa: E402
import youcom  # noqa: E402
import memory  # noqa: E402
import librarian  # noqa: E402
import live  # noqa: E402
import voice  # noqa: E402
from onboarding import QUESTIONS  # noqa: E402

app = FastAPI(title="dealer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _resume():
    swarm.resume()  # shipments and listings in flight before a restart carry on


@app.exception_handler(Exception)
async def _no_trace(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": type(exc).__name__})


class RunReq(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"ok": True, "demo_mode": os.getenv("DEMO_MODE", "0") == "1", "brain_enabled": brain.ENABLED,
            "llm_live": llm._client is not None, "sandboxed": False,
            "shift_running": swarm.running(), "shift": swarm.status(), "dealer_name": "Joe's Auto",
            "llm": llm.stats(), "youcom": youcom.stats()}


EVAL_FILE = Path(__file__).parent / "data" / "eval_result.json"


@app.get("/eval")
def get_eval():
    """Last brain OFF vs ON run written by eval.py; empty when it has never run."""
    if not EVAL_FILE.exists():
        return {"missing": True}
    r = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    return {k: r.get(k) for k in ("seed", "train_n", "heldout_n", "off", "on", "train", "playbook", "rows", "secs")} | {
        "ran_at": EVAL_FILE.stat().st_mtime, "running": _eval_running()}


_eval_proc = {"p": None}


def _eval_running() -> bool:
    p = _eval_proc["p"]
    if p is not None and p.poll() is not None:
        _eval_proc["p"] = None
        brain._loaded = False  # eval restored the live brain on disk; re-read it
    return _eval_proc["p"] is not None


@app.post("/eval/run")
def run_eval():
    """Re-run the offline eval (~20 s, no API calls) in its own process. Not during a shift: it swaps the brain file."""
    if swarm.running():
        return {"started": False, "error": "stop the shift first"}
    if _eval_running():
        return {"started": False, "error": "already running"}
    import subprocess
    import sys
    _eval_proc["p"] = subprocess.Popen([sys.executable, "eval.py"], cwd=Path(__file__).parent,
                                       env={**os.environ, "SIM_FAST": "1"},
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"started": True}


class ShiftReq(BaseModel):
    max_deals: int = 5  # 0 = continuous: the team keeps working until /shift/stop
    live: bool = False  # the first deal's seller is answered by a person in the browser


@app.post("/shift/start")
async def shift_start(req: ShiftReq = ShiftReq()):
    n = 0 if req.max_deals <= 0 else min(req.max_deals, 20)
    if _eval_running():
        return {"started": False, "error": "eval is running, try again in a few seconds"}
    return {"started": swarm.start(n, live_seller=req.live), "continuous": n == 0, "live": req.live}


@app.post("/shift/stop")
def shift_stop():
    swarm.stop()
    return {"stopped": True}


@app.get("/deals")
def deals():
    return swarm.public_deals()


@app.get("/deals/{deal_id}")
def deal(deal_id: str):
    d = next((x for x in swarm.public_deals() if x["id"] == deal_id), None)
    return d or JSONResponse(status_code=404, content={"error": "not found"})


@app.get("/briefing")
def briefing():
    return swarm.briefing()


class ResearchReq(BaseModel):
    question: str
    effort: str = "lite"


@app.post("/research")
async def research(req: ResearchReq):
    """Cited market answer for the concierge / owner (You.com Research, search fallback, disk cache)."""
    return await youcom.ask(req.question, req.effort)


@app.get("/youcom")
def youcom_stats():
    return youcom.stats()


@app.get("/events")
def events(since: int = 0):
    return swarm.EVENTS[since:]


@app.post("/run")
async def run(req: RunReq):
    return await loop.run(req.goal)


@app.get("/memory")
def get_memory():
    return memory.load()


class DecisionReq(BaseModel):
    yes: bool
    car: str = ""
    reason: str = ""


class SellerTextReq(BaseModel):
    text: str


@app.post("/deals/{deal_id}/seller-audio")
async def seller_audio(deal_id: str, request: Request):
    """Browser sends the seller's recorded answer (WAV). Parakeet transcribes it, then the negotiator reads it."""
    if deal_id not in live.PENDING:
        return {"ok": False, "error": "not waiting for a seller answer"}
    heard = voice.transcribe(await request.body())
    if heard is None:
        return {"ok": False, "error": "speech is off (no NVIDIA key), type the answer instead"}
    return live.answer(deal_id, heard)


@app.post("/deals/{deal_id}/seller-text")
def seller_text(deal_id: str, req: SellerTextReq):
    """Typed fallback for the seller's answer."""
    return live.answer(deal_id, req.text)


@app.get("/clips/{cid}.wav")
def clip(cid: str):
    """Agent speech for the browser player."""
    wav = voice.CLIPS.get(cid)
    return Response(wav, media_type="audio/wav") if wav else JSONResponse(status_code=404, content={"error": "not found"})


class FlagReq(BaseModel):
    reason: str = "Blocked by OpenShell policy"
    url: str = ""


@app.post("/deals/{deal_id}/flag")
def flag(deal_id: str, req: FlagReq):
    """Concierge (in the sandbox) reports a link it could not open. Becomes a red flag every agent recalls."""
    deal = swarm.DEALS.get(deal_id)
    sc = swarm._SC.get(deal_id) or {}
    party = f"seller:{(sc.get('seller') or {}).get('sid', deal_id)}"
    host = req.url.split("/")[2] if req.url.count("/") >= 2 else req.url
    brain.write("concierge", "party", party, "fact", True, attr="red_flag", confidence=0.9, source=f"openshell:{host or deal_id}")
    swarm.emit("concierge", "blocked", f"{req.reason}: {host or 'seller link'} (checked from the NemoClaw sandbox)",
               {"deal_id": deal_id, "url": req.url})
    if deal and deal["state"] not in ("dropped", "sold"):
        deal.update(state="dropped", drop_reason=f"red flag: {req.reason}")
    swarm.save()
    return {"ok": True, "deal_id": deal_id, "party": party}


@app.post("/deals/{deal_id}/approve")
async def decide(deal_id: str, req: DecisionReq):
    """Save the dealer's answer so the team acts on it next time, even if this deal is not in memory yet."""
    dealer_memory.record(req.car or deal_id, req.yes, req.reason)
    await swarm.approve(deal_id, req.yes, req.reason)
    return {"ok": True, "deal_id": deal_id, "saved": True}


class SetupReq(BaseModel):
    answers: dict[str, list[str]]


@app.post("/onboarding/answers")
def save_setup(req: SetupReq):
    """Save the dealer's setup choices; buying and selling read them from the brain."""
    return dealer_profile.save(req.answers)


class DealerReq(BaseModel):
    answers: dict[str, list[str]] = {}
    note: str = ""  # owner's free-text rule from the concierge, e.g. "no cars with more than 2 owners"


@app.put("/dealer")
def put_dealer(req: DealerReq):
    if req.note.strip():
        brain.write("owner", "dealer", "joes-auto", "note", req.note.strip()[:300], confidence=1.0, source="concierge")
        swarm.emit("owner", "write", f"Your rule saved: {req.note.strip()[:120]}", {})
    return dealer_profile.save(req.answers)


@app.get("/dealer")
def get_dealer():
    return dealer_profile.get()


@app.get("/onboarding/questions")
def onboarding_questions():
    return QUESTIONS


@app.get("/brain")
def get_brain():
    v = brain.view()
    tidy = next((e for e in reversed(swarm.EVENTS) if e["agent"] == "librarian" and "compaction" in e["data"]), None)
    return {**v, "stats": brain.stats(), "playbook": brain.playbook(), "tiers": librarian.tiers(),
            "last_tidy": tidy and {"ts": tidy["ts"], **tidy["data"]["compaction"], "lessons": len(tidy["data"]["lessons"])}}


@app.post("/brain/compact")
def compact_brain():
    return librarian.run(swarm.emit)


@app.get("/storefront", response_class=HTMLResponse)
def storefront():
    """Joe's public inventory page, written by the merchandiser agent."""
    cards = []
    for d in swarm.public_deals():
        if d["state"] not in ("listed", "sold"):
            continue
        l = d.get("listing") or {"title": d["car"], "description": "", "bullets": []}
        price = f"SOLD" if d["state"] == "sold" else f"${int(d.get('list_price') or 0):,}"
        bullets = "".join(f"<li>{html.escape(b)}</li>" for b in l.get("bullets", []))
        m = l.get("market") or {}
        if m.get("n"):
            bullets += f"<li><small>Priced against {m['n']} local listings (median ${int(m['median']):,}, via You.com)</small></li>"
        cards.append(f"<article class='{d['state']}'><h2>{html.escape(l['title'])}</h2><p class='price'>{price}</p>"
                     f"<p>{html.escape(l.get('description', ''))}</p><ul>{bullets}</ul><small>{d['id']}</small></article>")
    body = "".join(cards) or "<p>No cars listed yet. The team lists cars as they arrive on the lot.</p>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='5'>
<title>Joe's Auto - Stockton CA</title><style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{margin-bottom:.2rem}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}}
article{{border:1px solid #ddd;border-radius:10px;padding:1rem}} article.sold{{opacity:.5}}
.price{{font-size:1.4rem;font-weight:700;margin:.2rem 0}} small{{color:#888}}
</style></head><body><h1>Joe's Auto</h1><p>Used trucks and SUVs, Stockton CA. Listings written by our AI team.</p>
<div class='grid'>{body}</div></body></html>"""


@app.post("/brain/load/{name}")
def load_brain(name: str):
    try:
        return {"events": brain.load(name)}
    except FileNotFoundError as e:
        return {"error": str(e)}
