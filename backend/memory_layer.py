"""Three-tier memory for the agents.

Tier 1, private scratchpad: the raw chat in backend/data/conversations/<party>.md. Only its own agent reads it.
Tier 2, shared ledger: the brain. Agents share artifacts and status here, never raw chats.
Tier 3, long-term lessons: playbook lessons and MISTAKES.md lines, distilled by librarian.py.

consolidate() is the write-ahead step: when a negotiation ends, the chat is squeezed into one artifact line and a
status code. The artifact goes to the shared brain; the chat summary stays private to the agent that had it.
"""
import brain
import conversations
import llm


def status_of(result: dict) -> str:
    if result.get("closed"):
        return "SUCCESS"
    if "link" in (result.get("dropped") or "") or "red flag" in (result.get("dropped") or ""):
        return "BLOCKED"
    return "FAILED"


def artifact_of(result: dict) -> str:
    """One deterministic line every agent can rely on (numbers come from code, never the model)."""
    tactic, segment = result.get("tactic", "?").replace("_", " "), result.get("segment", "?").replace("_", " ")
    if result.get("closed"):
        return f"closed ${result['price']:,.0f} vs ask ${result['ask']:,.0f} in {result.get('rounds', 0)} rounds; {tactic} worked (seller type: {segment})"
    return f"no deal: {result.get('dropped') or 'unknown'}; tried {tactic} (seller type: {segment})"


async def _summary(party: str) -> str:
    """Cheap-model gist of the chat (fast tier). Empty when there is no key or the call fails."""
    tail = conversations.current(party)  # this deal's turns only: no talk, no gist
    if not tail or llm._client is None:
        return ""
    try:
        text = await llm.chat(
            "Summarise this used-car negotiation in one line (<= 25 words): what the other side cared about and what moved them. "
            "No prices.", tail, tier="fast", temperature=0.2, max_tokens=120)
        return text.strip().splitlines()[0][:200] if text else ""
    except Exception:
        return ""


async def consolidate(agent: str, party: str, deal_id: str, result: dict) -> dict:
    """Write-ahead consolidation after a deal. Returns {status, artifact, summary}."""
    status, artifact = status_of(result), artifact_of(result)
    # Tier 2: shared with every agent (buyer, sales desk, owner).
    brain.write(agent, "party", party, "note", f"[{status}] {artifact}", confidence=0.8, source=f"artifact:{deal_id}")
    brain.write(agent, "party", party, "fact", status, attr="last_status", confidence=0.8, source=f"artifact:{deal_id}")
    # Private detail: only the agent that held the conversation recalls it.
    summary = await _summary(party)
    if summary:
        brain.write(agent, "party", party, "note", f"chat gist: {summary}", confidence=0.6,
                    source=f"gist:{deal_id}", visible_to=[agent])
    # Tier 1 is closed: older turns squeezed, outcome stamped on the file.
    conversations.close(party, f"[{status}] {artifact}")
    return {"status": status, "artifact": artifact, "summary": summary}
