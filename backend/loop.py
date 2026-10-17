"""Persistent agent loop: define done -> work -> independent verify -> decide (continue/replan/stop/ping human)."""
import hashlib

import llm
import memory

MAX_ITERS = 4


async def define_done(goal: str, lessons: list[str]) -> list[str]:
    out = await llm.chat_json(
        "You write the definition of done. Turn the goal into 3-5 concrete, testable checks. "
        "Return a JSON array of strings.",
        f"Goal: {goal}\nPast lessons: {lessons}",
    )
    return out if isinstance(out, list) else []


async def work(goal: str, checks: list[str], lessons: list[str], feedback: str) -> str:
    return await llm.chat(
        "You are the worker agent. Satisfy every check. Be concrete.",
        f"Goal: {goal}\nChecks: {checks}\nShared memory lessons: {lessons}\nVerifier feedback: {feedback or 'none'}",
    )


async def verify(goal: str, checks: list[str], output: str) -> list[dict]:
    out = await llm.chat_json(
        "You are an independent verifier. Do not trust the worker. For each check return "
        '{"results": [{"check": str, "pass": bool, "reason": str}]}.',
        f"Goal: {goal}\nChecks: {checks}\nOutput:\n{output}",
    )
    return out.get("results", []) if isinstance(out, dict) else []


async def run(goal: str) -> dict:
    mem = memory.load()
    lessons = mem["lessons"]
    checks = await define_done(goal, lessons)
    trace, seen, feedback, status, output = [], set(), "", "stopped", ""

    for i in range(1, MAX_ITERS + 1):
        output = await work(goal, checks, lessons, feedback)
        results = await verify(goal, checks, output)
        passed = bool(results) and all(r.get("pass") for r in results)
        digest = hashlib.sha1(output.encode()).hexdigest()
        drifting = digest in seen  # identical output twice = looping
        seen.add(digest)
        decision = "done" if passed else "replan" if drifting else "continue"
        trace.append({"iter": i, "output": output, "results": results, "decision": decision})
        if passed:
            status = "done"
            break
        if drifting:
            checks = await define_done(goal + " (previous plan looped; rethink approach)", lessons)
        feedback = "; ".join(r.get("reason", "") for r in results if not r.get("pass"))
    else:
        status = "needs_human"  # budget exhausted, rarely ping a human

    lesson = await llm.chat(
        "Write ONE short reusable lesson (<=20 words) from this run for the shared team memory.",
        f"Goal: {goal}\nStatus: {status}\nTrace: {[(t['iter'], t['decision']) for t in trace]}",
    )
    memory.add_lesson(mem, lesson.strip())
    result = {"goal": goal, "status": status, "checks": checks, "output": output, "trace": trace}
    memory.log_run(mem, {"goal": goal, "status": status, "iters": len(trace)})
    memory.save(mem)
    return result
