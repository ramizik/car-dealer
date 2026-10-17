"""Per-party conversation log kept as Markdown, so agents read a short tail instead of re-sending whole chats.

One file per party in backend/data/conversations/ (git-ignored: it holds people's messages).
Phone numbers are masked before anything is written. Only the last KEEP turns go into a prompt;
older turns are squeezed to one line each in the file's "Earlier" section.
"""
import re
from pathlib import Path

import voice

ROOT = Path(__file__).parent / "data" / "conversations"
KEEP = 6  # verbatim turns sent to the model
EARLIER_CHARS = 80  # per older turn, in the file
EARLIER_MAX = 20  # oldest lines are dropped beyond this, so the file stays small
PHONE_ANY = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def _path(party: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", party)
    return ROOT / f"{safe}.md"


def _mask(text: str) -> str:
    """Replace any phone-like run with its masked form, so the file never holds a full number."""
    def repl(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return voice.mask_phone(f"+{digits}") if len(digits) >= 10 else m.group(0)
    return PHONE_ANY.sub(repl, text)


def append(party: str, role: str, text: str, tag: str = "") -> None:
    """Add one turn. role is 'agent' or 'seller' or 'buyer'."""
    ROOT.mkdir(parents=True, exist_ok=True)
    line = f"- **{role}**{f' ({tag})' if tag else ''}: {_mask(text.strip())}\n"
    path = _path(party)
    if not path.exists():
        path.write_text(f"# {party}\n\n## Turns\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    _compact(path)


def _compact(path: Path) -> None:
    """Move turns older than KEEP into the Earlier section, one short line each. Earlier lines are kept."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    t_idx = lines.index("## Turns\n")
    earlier = [ln for ln in lines[:t_idx] if ln.startswith("- **")]
    turns = [ln for ln in lines[t_idx + 1:] if ln.startswith("- **")]
    if len(turns) <= KEEP:
        return
    old, recent = turns[:-KEEP], turns[-KEEP:]
    squeezed = [ln.rstrip()[:EARLIER_CHARS] + "\n" for ln in old]
    body = [lines[0], "\n", "## Earlier (short)\n"] + (earlier + squeezed)[-EARLIER_MAX:] + ["\n", "## Turns\n"] + recent
    path.write_text("".join(body), encoding="utf-8")


def recent(party: str, n: int = KEEP) -> str:
    """The text to put in a prompt: earlier summary (if any) plus the last n turns. Empty if no history."""
    path = _path(party)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    turns = [ln for ln in text.splitlines() if ln.startswith("- **")][-n:]
    return "\n".join(turns)


def close(party: str, outcome: str) -> None:
    """End of a deal: squeeze every turn into the Earlier section and stamp the outcome. Next chat starts clean."""
    path = _path(party)
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    t_idx = lines.index("## Turns\n")
    earlier = [ln for ln in lines[:t_idx] if ln.startswith("- **")]
    turns = [ln for ln in lines[t_idx + 1:] if ln.startswith("- **")]
    squeezed = [ln.rstrip()[:EARLIER_CHARS] + "\n" for ln in turns]
    stamp = f"- **outcome**: {_mask(outcome)}\n"  # kept like a turn, so later compactions keep it too
    body = [lines[0], "\n", "## Earlier (short)\n"] + (earlier + squeezed)[-(EARLIER_MAX - 1):] + [stamp, "\n", "## Turns\n"]
    path.write_text("".join(body), encoding="utf-8")
