from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import brain  # noqa: E402
import loop  # noqa: E402
import memory  # noqa: E402

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
