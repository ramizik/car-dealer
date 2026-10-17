"""Three-tier memory checks. Run: cd backend && python test_memory_tiers.py (plain asserts, no LLM calls)."""
import asyncio
import tempfile
from pathlib import Path

import brain
import conversations
import librarian
import llm
import memory_layer
import skills
import vector_memory

# isolate from real data
tmp = Path(tempfile.mkdtemp())
brain.DIR, brain.LOG, brain.SNAPSHOTS = tmp, tmp / "events.jsonl", tmp / "snapshots"
conversations.ROOT = tmp / "conversations"
skills.ROOT = tmp / "skills"
vector_memory.PATH = tmp / "vectors.jsonl"
brain.reset()


async def fake_chat(*a, **k):
    return "seller wanted cash today and a quick pickup"
llm.chat, llm._client = fake_chat, object()  # gist path runs without a key


def deal(i, closed, tactic="fast_cash_pickup", segment="motivated_private", dropped=""):
    r = {"closed": closed, "tactic": tactic, "segment": segment, "rounds": 3, "ask": 15000}
    return r | ({"price": 13200} if closed else {"dropped": dropped})


async def main():
    # Tier 1: private chat file, closed with outcome stamp
    party = "seller:s1"
    for t in range(8):
        conversations.append(party, "agent" if t % 2 == 0 else "seller", f"turn {t} call me at 415 555 0199")
    assert "555 0199" not in conversations._path(party).read_text(encoding="utf-8"), "phone must be masked"
    assert len(conversations.recent(party).splitlines()) == conversations.KEEP
    m = await memory_layer.consolidate("negotiator", party, "D-1", deal(1, True))
    assert m["status"] == "SUCCESS" and "closed $13,200" in m["artifact"]
    assert "**outcome**: [SUCCESS]" in conversations.recent(party), "next chat with this seller sees the last outcome"

    # Tier 2: artifact shared with every agent, gist only with the negotiator
    neg = "\n".join(brain.recall("party", keys=[party], agent="negotiator"))
    other = "\n".join(brain.recall("party", keys=[party], agent="merchandiser"))
    assert "[SUCCESS]" in neg and "[SUCCESS]" in other, "artifact is shared"
    assert "chat gist" in neg and "chat gist" not in other, "gist is private"
    m2 = await memory_layer.consolidate("negotiator", party, "D-1b", deal(1, False, dropped="sales desk: profit too low"))
    assert m2["summary"] == "", "no talk this deal, so no gist (old closed chat must not be re-summarised)"

    # Tier 3: lessons from 3+ tries, mistakes from 2+ repeated misses
    for i in range(2, 6):
        p = f"seller:s{i}"
        brain.write("negotiator", "playbook", "fast_cash_pickup|motivated_private", "counter", {"tries": 1, "wins": 1})
        await memory_layer.consolidate("negotiator", p, f"D-{i}", deal(i, False, dropped="seller walked away"))
    out = librarian.run()
    assert any("fast cash pickup wins 4/4" in l for l in out["lessons"]), out["lessons"]
    assert any("seller walked away" in l for l in skills.mistakes("buyer/outreach")), "mistake reaches MISTAKES.md"
    pb = "\n".join(brain.recall("playbook", keys=["|motivated_private"], agent="negotiator"))
    assert "lesson:" in pb, "negotiator recalls the lesson next deal"

    # Tier 3 vector store: similar past deals, mistakes visible to the negotiator only
    assert out["vectors_added"] > 0
    hits = vector_memory.search("seller walked away no deal", agent="negotiator", scopes=["deals", "lessons", "mistakes"])
    assert hits and any("walked away" in h["text"] for h in hits), hits
    assert not vector_memory.search("seller walked away", agent="merchandiser", scopes=["mistakes"]), "mistakes are negotiator-only"
    assert not any("chat gist" in r["text"] for r in vector_memory._load()), "private gists never reach the vector store"

    # compaction never changes what agents recall
    before = brain.recall(brain.SCOPES, agent="negotiator", budget_chars=5000)
    c = librarian.compact()
    assert c["applied"] and brain.recall(brain.SCOPES, agent="negotiator", budget_chars=5000) == before
    print(f"memory tiers ok: T1 masked+closed, T2 shared/private split, T3 {len(out['lessons'])} lesson(s) + "
          f"{len(out['mistakes'])} mistake(s), {out['vectors_added']} vectors, compaction {c['events_before']}->{c['events_after']} events, recall unchanged")


asyncio.run(main())
