# .claude/skills/

Shared agent skills for the team. Checked in on purpose (rest of `.claude/` stays gitignored).

Auto-loaded with no setup:
- **Claude Code** loads project skills from `.claude/skills/<name>/SKILL.md`.
- **Cursor** loads `.claude/skills/` too (alongside `.cursor/skills/` and `.agents/skills/`). Check Settings > Skills or type `/` in Agent chat.
- Any other agent: point it at the `SKILL.md` file.

## Skills
| Skill | Use for |
|---|---|
| `crusoe-recursive-agents-hackathon/` | Event + Crusoe Managed Inference: endpoint, model IDs, rate limits, reasoning toggles. Read before touching `backend/llm.py`. |
| `nemoclaw-user-guide/` | NemoClaw install, onboard, policies, troubleshooting (points to live NVIDIA docs + docs MCP). |
| `nemotron-policy-generator/` | Custom safety policies for Nemotron content-safety guardrails. |
| `nemotron-retrieval-recipes/` | Nemotron embedding / reranking recipes. |
| `nemotron-speech/` | Nemotron Speech (Riva) ASR / TTS / NMT NIMs. |
| `nemotron-customize/` | Nemotron fine-tuning / alignment / eval pipelines (heavy; mostly out of hackathon scope). |

## Provenance
NVIDIA skills copied unmodified from https://github.com/NVIDIA/skills (`skills/<name>`), commit `4fc9cf6cec785070e0bf5bb4aa6c992f71b1c97e` (2026-10-17). Licenses: `NVIDIA-LICENSE-APACHE`, `NVIDIA-LICENSE-CC-BY-4.0`. To update, re-copy the folder from that repo.

## Rules
- No keys, tokens, or `.env` contents in any file here.
- New skill = new folder with `SKILL.md` (frontmatter `name` + `description`).
