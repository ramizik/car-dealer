from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import brain  # noqa: E402
import dealer_memory  # noqa: E402
import dealer_profile  # noqa: E402
import loop  # noqa: E402
import memory  # noqa: E402
from onboarding import QUESTIONS  # noqa: E402

app = FastAPI(title="dealer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RunReq(BaseModel):
    goal: str


@app.get("/health")
def health():
    return {"ok": True}


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
def decide(deal_id: str, req: DecisionReq):
    """Save the dealer's answer so the team acts on it next time, even if this deal is not in memory yet."""
    dealer_memory.record(req.car or deal_id, req.yes, req.reason)
    return {"ok": True, "deal_id": deal_id, "saved": True}


class SetupReq(BaseModel):
    answers: dict[str, list[str]]


@app.post("/onboarding/answers")
def save_setup(req: SetupReq):
    """Save the dealer's setup choices; buying and selling read them from the brain."""
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
