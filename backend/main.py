from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import brain  # noqa: E402
import llm  # noqa: E402
import dealer_memory  # noqa: E402
import dealer_profile  # noqa: E402
import loop  # noqa: E402
import swarm  # noqa: E402
import memory  # noqa: E402
from onboarding import QUESTIONS  # noqa: E402

app = FastAPI(title="dealer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
            "llm": llm.stats()}


EVAL_FILE = Path(__file__).parent / "data" / "eval_result.json"


@app.get("/eval")
def get_eval():
    """Last brain OFF vs ON run written by eval.py; empty when it has never run."""
    if not EVAL_FILE.exists():
        return {"missing": True}
    r = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    return {k: r.get(k) for k in ("seed", "train_n", "heldout_n", "off", "on", "train", "playbook", "secs")} | {
        "ran_at": EVAL_FILE.stat().st_mtime}


class ShiftReq(BaseModel):
    max_deals: int = 5


@app.post("/shift/start")
async def shift_start(req: ShiftReq = ShiftReq()):
    return {"started": swarm.start(max(1, min(req.max_deals, 20)))}


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


@app.put("/dealer")
def put_dealer(req: SetupReq):
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
    return {**v, "stats": brain.stats(), "playbook": brain.playbook()}


@app.post("/brain/load/{name}")
def load_brain(name: str):
    try:
        return {"events": brain.load(name)}
    except FileNotFoundError as e:
        return {"error": str(e)}
