"""Phone calls through Twilio: dial the dealer number, talk to the buyer or seller agent.

Turn loop (plain HTTP webhooks, no websockets):
  /twilio/voice -> greeting + "press 1 selling, 2 buying" -> /twilio/role -> agent's first question
  -> caller speaks -> /twilio/turn: Parakeet transcribes the recording, the agent answers, Magpie speaks it -> repeat.
Without NVIDIA_API_KEY it falls back to Twilio's own speech recognition (<Gather input=speech>) and <Say>.

Safety: only TWILIO_ALLOWED_CALLER may use it (everyone else hears one line and is hung up on), every request must
carry a valid Twilio signature, the agent never commits a price on a call, and the number is masked in logs.
Env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_ALLOWED_CALLER (+1...), PUBLIC_BASE_URL (https://...).
"""
import audioop
import base64
import hashlib
import hmac
import io
import os
import re
import time
import uuid
import wave
from urllib.parse import parse_qs
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

import brain
import conversations
import llm
import voice

router = APIRouter(prefix="/twilio")

MAX_TURNS = 10
SESSIONS: dict[str, dict] = {}  # CallSid -> {role, turns, party, started}
AUDIO: dict[str, tuple[float, bytes]] = {}  # id -> (created, wav bytes); served once to Twilio, then expired

# Call scripts: the agent works through these questions in order, one per turn, and never quotes a price.
SCRIPTS = {
    "seller": {
        "label": "you're selling a car to us",
        "skill": "buyer/outreach",
        "opening": "Great, thanks for calling about selling your car. What's the year, make and model?",
        "questions": [
            "Roughly how many miles are on it?",
            "Is the title clean, and has it been in any accidents?",
            "How many keys do you have, and is there a loan on it?",
            "What's got you selling it?",
            "When could we come and see it?",
            "If we could pick it up this week, what's the lowest number you'd take?",
        ],
        "closing": "Thanks. The desk will check the market value and text you an offer. Anything else before I let you go?",
    },
    "buyer": {
        "label": "you want to buy a car",
        "skill": "seller/enquiry",
        "opening": "Great, thanks for calling about buying a car. Which car caught your eye, or what are you looking for?",
        "questions": [
            "What budget would you rather not go over?",
            "What's the one must-have, like four-wheel drive or third-row seats?",
            "When are you hoping to buy?",
            "Do you have a trade-in?",
            "Are you paying cash or looking at financing?",
            "What zip code are you in, in case we deliver?",
        ],
        "closing": "Thanks. The desk will text you a few options and a time to see them. Anything else before I let you go?",
    },
}
GREETING = ("Hi, this is the AI assistant for Joe's Auto. A team member reviews every deal. "
            "Press 1 if you're selling a car to us, or press 2 if you want to buy one.")
BYE = re.compile(r"\b(bye|goodbye|that's all|thats all|no thanks|stop|hang up)\b", re.I)


# ---------- plumbing ----------

def _env(k: str) -> str:
    return os.getenv(k, "")


def _twiml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>', media_type="application/xml")


def _url(path: str) -> str:
    return _env("PUBLIC_BASE_URL").rstrip("/") + path


def _valid_signature(url: str, params: dict[str, str], signature: str) -> bool:
    """Twilio's scheme: HMAC-SHA1 of the full URL plus sorted key+value pairs, base64, keyed by the auth token."""
    token = _env("TWILIO_AUTH_TOKEN")
    if not token or not signature:
        return False
    data = url + "".join(k + params[k] for k in sorted(params))
    digest = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(digest, signature)


async def _params(request: Request) -> dict[str, str] | None:
    """Form fields from Twilio, or None if the signature does not match."""
    body = (await request.body()).decode()
    params = {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}
    url = _url(request.url.path) + (f"?{request.url.query}" if request.url.query else "")
    return params if _valid_signature(url, params, request.headers.get("X-Twilio-Signature", "")) else None


def _allowed(params: dict[str, str]) -> bool:
    caller = voice.extract_phone(params.get("From", "")) or ""
    return bool(caller) and caller == voice.extract_phone(_env("TWILIO_ALLOWED_CALLER"))


def _parakeet() -> bool:
    return bool(_env("NVIDIA_API_KEY"))


def _speak(text: str) -> str:
    """<Play> Magpie audio when available, otherwise Twilio's <Say>."""
    pcm = voice.speak(text, sample_rate_hz=22050) if _parakeet() else None
    if pcm:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(pcm)
        aid = uuid.uuid4().hex
        AUDIO[aid] = (time.time(), buf.getvalue())
        return f"<Play>{escape(_url(f'/twilio/audio/{aid}.wav'))}</Play>"
    return f'<Say voice="Polly.Joanna">{escape(text)}</Say>'


def _listen() -> str:
    action = escape(_url("/twilio/turn"))
    if _parakeet():
        return f'<Record action="{action}" maxLength="15" timeout="2" playBeep="false" trim="trim-silence"/>'
    return f'<Gather input="speech" action="{action}" speechTimeout="auto" language="en-US"/>' \
           f'<Redirect method="POST">{action}</Redirect>'


async def _transcribe(params: dict[str, str]) -> str:
    """Parakeet on the call recording (8 kHz -> 16 kHz), or Twilio's SpeechResult in fallback mode."""
    if "SpeechResult" in params or not params.get("RecordingUrl"):
        return params.get("SpeechResult", "").strip()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(params["RecordingUrl"] + ".wav", auth=(_env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")))
            r.raise_for_status()
        with wave.open(io.BytesIO(r.content)) as w:
            pcm, rate, width = w.readframes(w.getnframes()), w.getframerate(), w.getsampwidth()
        if width != 2:
            pcm = audioop.lin2lin(pcm, width, 2)
        if rate != 16000:
            pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
        return (voice.transcribe(pcm, sample_rate_hz=16000) or "").strip()
    except Exception:
        return ""


async def _reply(s: dict, heard: str) -> str:
    """Next agent line: the script's next question, phrased by the model when it is live. Never a price."""
    script = SCRIPTS[s["role"]]
    i = s["turns"] - 1
    planned = script["questions"][i] if i < len(script["questions"]) else script["closing"]
    if llm._client is None:
        return planned
    try:
        text = await llm.chat(
            "You are a friendly phone assistant for a used-car dealership. Reply in at most 2 short spoken sentences. "
            "Briefly acknowledge what the caller said, then ask the planned question. Never quote, offer or agree to any "
            "price; say the desk will confirm by text. Never ask for card, bank or ID numbers. No lists, no emojis.",
            f"Call so far:\n{conversations.recent(s['party'])}\n\nCaller just said: {heard}\nPlanned question: {planned}",
            tier="smart", temperature=0.4, max_tokens=1024)
        text = (text or "").strip()
        return planned if not text or re.search(r"\$\s?\d", text) else text[:400]  # no prices on calls
    except Exception:
        return planned


# ---------- webhooks ----------

@router.post("/voice")
async def incoming(request: Request):
    params = await _params(request)
    if params is None:
        return Response(status_code=403)
    if not _allowed(params):
        return _twiml("<Say>Sorry, this line is not open yet. Goodbye.</Say><Hangup/>")
    sid = params.get("CallSid", uuid.uuid4().hex)
    SESSIONS[sid] = {"role": None, "turns": 0, "party": f"caller:{sid[-8:]}", "started": time.time()}
    gather = f'<Gather numDigits="1" action="{escape(_url("/twilio/role"))}" timeout="6">{_speak(GREETING)}</Gather>'
    return _twiml(gather + f'<Redirect method="POST">{escape(_url("/twilio/voice"))}</Redirect>')


@router.post("/role")
async def role(request: Request):
    params = await _params(request)
    if params is None:
        return Response(status_code=403)
    s = SESSIONS.get(params.get("CallSid", ""))
    if s is None or not _allowed(params):
        return _twiml("<Hangup/>")
    s["role"] = "seller" if params.get("Digits") == "1" else "buyer"
    opening = SCRIPTS[s["role"]]["opening"]
    conversations.append(s["party"], "agent", opening, tag="call")
    return _twiml(_speak(opening) + _listen())


@router.post("/turn")
async def turn(request: Request):
    params = await _params(request)
    if params is None:
        return Response(status_code=403)
    s = SESSIONS.get(params.get("CallSid", ""))
    if s is None or not s.get("role") or not _allowed(params):
        return _twiml("<Hangup/>")
    heard = await _transcribe(params)
    if not heard:
        return _twiml(_speak("Sorry, I didn't catch that. Could you say it again?") + _listen())
    conversations.append(s["party"], s["role"], heard, tag="call")
    s["turns"] += 1
    if BYE.search(heard) or s["turns"] > MAX_TURNS:
        bye = "Thanks for calling Joe's Auto. The desk will text you soon. Goodbye."
        conversations.append(s["party"], "agent", bye, tag="call")
        brain.write("phone", "party", s["party"], "note", f"[CALL] {s['role']} call, {s['turns']} turns",
                    confidence=0.6, source="twilio")
        SESSIONS.pop(params.get("CallSid", ""), None)
        return _twiml(_speak(bye) + "<Hangup/>")
    answer = await _reply(s, heard)
    conversations.append(s["party"], "agent", answer, tag="call")
    return _twiml(_speak(answer) + _listen())


@router.get("/audio/{aid}.wav")
def audio(aid: str):
    now = time.time()
    for k in [k for k, (t, _) in AUDIO.items() if now - t > 300]:  # expire after 5 minutes
        AUDIO.pop(k, None)
    item = AUDIO.get(aid)
    return Response(item[1], media_type="audio/wav") if item else Response(status_code=404)


@router.get("/status")
def status():
    """Setup check for the dashboard or the setup script. Shows which pieces are configured, never their values."""
    return {"twilio_keys": bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN")),
            "allowed_caller_set": bool(voice.extract_phone(_env("TWILIO_ALLOWED_CALLER"))),
            "public_base_url": _env("PUBLIC_BASE_URL") or None,
            "speech": "parakeet+magpie" if _parakeet() else "twilio built-in (set NVIDIA_API_KEY for Parakeet)",
            "agent_voice_model": "live" if llm._client is not None else "scripted questions only",
            "active_calls": len(SESSIONS)}
