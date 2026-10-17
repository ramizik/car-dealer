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
6. Write a `call_request` event: party, dealer, reason, preferred time window. The agents never dial out. The only live line is the dealer's own Twilio number, locked to the dealer's phone (see Phone line below).
7. Tell the person when they will hear back, and what the call is about.

## Phone line (Twilio, `backend/phone.py`)

The dealer dials the Twilio number and plays the seller or buyer. Only `TWILIO_ALLOWED_CALLER` gets through; every request must carry a valid Twilio signature. Setup on the droplet: `bash nemoclaw/phone-setup.sh` (public HTTPS for `/twilio/*` only). Check: `GET /twilio/status`.

Each turn: the caller's recording goes to Parakeet, the agent answers in at most 2 sentences, Magpie speaks it. Without `NVIDIA_API_KEY`, Twilio's own speech recognition and voice are used instead.

## Call scripts (the code copy lives in `SCRIPTS` in `backend/phone.py`)

Greeting: "Hi, this is the AI assistant for Joe's Auto. A team member reviews every deal. Press 1 if you're selling a car to us, or press 2 if you want to buy one."

**Seller call (we buy), one question per turn:**
1. Year, make and model.
2. Rough mileage.
3. Clean title? Any accidents?
4. How many keys? Any loan on it?
5. Why selling?
6. When can we see it?
7. Lowest number if we pick it up this week.
Close: "The desk will check the market value and text you an offer."

**Buyer call (we sell), one question per turn:**
1. Which car, or what are they looking for?
2. Budget they'd rather not go over.
3. The one must-have.
4. When they want to buy.
5. Trade-in?
6. Cash or financing?
7. Zip code, in case we deliver.
Close: "The desk will text you a few options and a time to see them."

Call rules: acknowledge what they said, then ask the next question. Never quote, offer or agree to a price on a call (a reply containing a dollar amount is replaced by the planned question). Never ask for card, bank or ID numbers. "Bye", "stop" or 10 turns ends the call.

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
