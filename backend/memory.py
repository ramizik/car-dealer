"""Shared brain: one JSON file every agent reads before work and appends to after."""
import json
import time
from pathlib import Path

PATH = Path(__file__).parent / "data" / "memory.json"
MAX_LESSONS = 20  # keep lean


def load() -> dict:
    if PATH.exists():
        return json.loads(PATH.read_text())
    return {"lessons": [], "runs": []}


def save(mem: dict) -> None:
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps(mem, indent=2))


def add_lesson(mem: dict, lesson: str) -> None:
    if lesson and lesson not in mem["lessons"]:
        mem["lessons"] = (mem["lessons"] + [lesson])[-MAX_LESSONS:]


def log_run(mem: dict, run: dict) -> None:
    mem["runs"].append({**run, "ts": time.time()})
    mem["runs"] = mem["runs"][-50:]
