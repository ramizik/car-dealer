"""Per-agent skill files: read before work, append mistakes after (see skills/README.md).

load("buyer/outreach") -> own SKILL.md + shared playbook + top MISTAKES.md lines, capped.
record_mistake("buyer/outreach", "...") -> prepends one dated line (dedup bumps hits).
"""
import re
import time
from pathlib import Path

ROOT = Path(__file__).parent / "skills"
SHARED = {"buyer/outreach": ["shared/sales-playbook"], "seller/enquiry": ["shared/sales-playbook"]}
VOICE = "shared/voice-calls"
TOP_MISTAKES = 5
BUDGET = 4000  # chars of skill text per agent call


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def mistakes(agent: str, n: int = TOP_MISTAKES) -> list[str]:
    lines = [l.strip() for l in _read(ROOT / agent / "MISTAKES.md").splitlines() if l.strip().startswith("- ")]
    return lines[:n]


def load(agent: str, voice: bool = False, budget: int = BUDGET) -> dict:
    """{agent, text, mistakes, files} - text is ready to drop into a system prompt."""
    names = [agent] + SHARED.get(agent, []) + ([VOICE] if voice else [])
    files = [n for n in names if (ROOT / n / "SKILL.md").exists()]
    top = mistakes(agent)
    head = ("Known mistakes (newest first):\n" + "\n".join(top) + "\n\n") if top else ""
    body = "\n\n".join(_read(ROOT / n / "SKILL.md") for n in files)
    return {"agent": agent, "text": (head + body)[:budget], "mistakes": top, "files": [f"{n}/SKILL.md" for n in files]}


def record_mistake(agent: str, line: str) -> str:
    """Prepend '- YYYY-MM-DD <line> (hits: n)'. Same line again bumps hits instead of duplicating."""
    path = ROOT / agent / "MISTAKES.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        old = _read(path).splitlines()
        header = [l for l in old if l.startswith("#")] or [f"# {agent} mistakes"]
        items = [l for l in old if l.startswith("- ")]
        hits = 1
        for l in items:
            if line in l:
                m = re.search(r"\(hits: (\d+)\)", l)
                hits = (int(m.group(1)) if m else 1) + 1
                items.remove(l)
                break
        entry = f"- {time.strftime('%Y-%m-%d')} {line} (hits: {hits})"
        path.write_text("\n".join(header + [""] + [entry] + items) + "\n", encoding="utf-8")
        return entry
    except Exception:
        return ""


def catalog() -> list[dict]:
    """All agents with a SKILL.md, for the UI."""
    return [{"agent": p.parent.relative_to(ROOT).as_posix(), "mistakes": len(mistakes(p.parent.relative_to(ROOT).as_posix(), 999))}
            for p in sorted(ROOT.glob("*/*/SKILL.md"))]
