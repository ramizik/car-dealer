# Voice calls (buyer and seller agents)

**Job:** let buyer and seller agents speak with people by voice, and once a person is interested, ask for a callback number and set up a call. Voice is an extra channel on top of text chat; the same rules apply.

## Models

- **Parakeet** (speech to text): caller audio into a transcript. `backend/voice.py: transcribe()`.
- **Magpie** (text to speech): agent reply into audio. `backend/voice.py: speak()`.
- Brain reply in between uses the agent's own tier (`backend/agent_tiers.py`).

Both are NVIDIA cloud calls via `nvidia-riva-client` with `NVIDIA_API_KEY`. With no key, both return `None` and the agent stays in text.

## Flow

1. Person says they are interested (a "yes, I'm selling", "is it still available", "can I come see it").
2. Agent confirms in the same channel: "Happy to set up a call. What number should we ring you on?"
3. On reply, `extract_phone(text)` returns `+1XXXXXXXXXX` or `None`. If `None`, ask once more, then fall back to text.
4. Confirm the number back, masked: "I have +1******0142. Is that right?" Only save it after a clear yes.
5. Save to `party` as `phone` with `consent: true`, `consent_at`, and the channel it came from.
6. Write a `call_request` event: party, dealer, reason, preferred time window. **No call is placed by the hackathon build.** The dealer's desk sees the request on the dashboard.
7. Tell the person when they will hear back, and what the call is about.

## Rules

- Ask for a number only when the person is interested. Never ask for it up front.
- Say why: "so the desk can call you about the car".
- Never log or print the full number. Use `mask_phone()` in logs, UI and the brain view.
- Never put a number in a URL, query string or shared link.
- Never share a number with another party, and never use it for anything except this call request.
- Disclosure applies on voice too: the first spoken line says the caller is an AI assistant for the dealer, and a team member reviews the deal.
- If the person says "stop" or "don't call", set `party.call_opt_out = true` and stop calling requests.
- Voice reply length: one or two short sentences per turn. Long speech loses people.

## Demo rules

- Hackathon build: voice runs on the simulator. Real calls to real people are out of scope.
- If Parakeet or Magpie fails, the agent keeps working in text. Never show an error or a blank screen.
- Show the Parakeet transcript and the Magpie reply text next to the audio in the UI.
