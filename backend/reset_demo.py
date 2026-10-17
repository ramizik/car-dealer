"""Reset for a demo run: wipe deals and the feed, load the cold brain (python reset_demo.py [cold|warm])."""
import sys

import brain
import swarm

name = sys.argv[1] if len(sys.argv) > 1 else "cold"
swarm.STATE_FILE.unlink(missing_ok=True)
if name == "cold" and not (brain.SNAPSHOTS / "cold.jsonl").exists():
    brain.reset()
    brain.snapshot("cold")  # empty brain: the team learns from zero on stage
print(f"state cleared, brain '{name}' loaded: {brain.load(name)} events")
