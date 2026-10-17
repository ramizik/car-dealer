"""Voice for buyer and seller agents: Parakeet (speech-to-text) and Magpie (text-to-speech) on NVIDIA cloud.

Call flow: caller audio -> transcribe() -> LLM reply (smart tier) -> speak() -> audio back.
Once a person is interested, the agent asks for a callback number and calls extract_phone().
No real call is placed from this module; it only records a call request.

Without NVIDIA_API_KEY, transcribe() and speak() return None so the caller can fall back to text.
Function IDs come from NVCF at runtime (see .claude/skills/nemotron-speech); override with env.
"""
import json
import os
import re
import urllib.request

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
SERVER = os.getenv("NVIDIA_SPEECH_SERVER", "grpc.nvcf.nvidia.com:443")
ASR_MODEL = os.getenv("NVIDIA_ASR_MODEL", "parakeet-ctc-1_1b-asr")  # NVCF name without the "ai-" prefix
TTS_MODEL = os.getenv("NVIDIA_TTS_MODEL", "magpie-tts-multilingual")
VOICE = os.getenv("NVIDIA_TTS_VOICE", "")  # set to a name from --list-voices

_function_ids: dict[str, str] = {}

# US-style numbers: optional +1, 10 digits, with spaces, dots or dashes. Keeps the number, drops the words around it.
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")


def extract_phone(text: str) -> str | None:
    """Return a normalised +1XXXXXXXXXX number from a chat or transcript line, or None."""
    m = _PHONE_RE.search(text or "")
    if not m:
        return None
    area, exchange, line = m.groups()
    if area[0] in "01" or exchange[0] in "01":  # not a valid NANP number
        return None
    return f"+1{area}{exchange}{line}"


def mask_phone(phone: str) -> str:
    """For logs and the UI: +1******1234."""
    return f"{phone[:2]}******{phone[-4:]}" if phone else ""


# Full callback numbers stay in this process only (never in the brain or logs). Lost on restart by design.
CALLBACKS: dict[str, str] = {}


def record_callback(party: str, phone: str) -> str:
    """Keep the full number for the call desk, return the masked form for the brain and UI."""
    CALLBACKS[party] = phone
    return mask_phone(phone)


def _function_id(model: str) -> str | None:
    """Look up an active NVCF function ID by model name, once per process."""
    if model in _function_ids:
        return _function_ids[model]
    req = urllib.request.Request(
        "https://api.nvcf.nvidia.com/v2/nvcf/functions?visibility=public,authorized",
        headers={"Authorization": f"Bearer {NVIDIA_API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        functions = json.load(r).get("functions", [])
    for f in functions:
        if f.get("status") == "ACTIVE" and f.get("name", "").removeprefix("ai-") == model:
            _function_ids[model] = f["id"]
            return f["id"]
    return None


def _auth(fid: str):
    import riva.client  # lazy: only needed with a key

    md = [["function-id", fid], ["authorization", f"Bearer {NVIDIA_API_KEY}"]]
    return riva.client.Auth(uri=SERVER, use_ssl=True, metadata_args=md)


def transcribe(wav: bytes, sample_rate_hz: int = 16000) -> str | None:
    """Parakeet ASR on a WAV clip. Returns the transcript, or None when offline or on error."""
    if not NVIDIA_API_KEY:
        return None
    try:
        import riva.client

        fid = _function_id(ASR_MODEL)
        if not fid:
            return None
        asr = riva.client.ASRService(_auth(fid))
        cfg = riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate_hz,
            language_code="en-US",
            max_alternatives=1,
            enable_automatic_punctuation=True,
        )
        resp = asr.offline_recognize(wav, cfg)  # Parakeet CTC serves offline recognition for short clips
        return resp.results[0].alternatives[0].transcript if resp.results else ""
    except Exception:
        return None


def speak(text: str, sample_rate_hz: int = 44100) -> bytes | None:
    """Magpie TTS. Returns LINEAR_PCM audio bytes, or None when offline or on error."""
    if not NVIDIA_API_KEY:
        return None
    try:
        import riva.client

        fid = _function_id(TTS_MODEL)
        if not fid:
            return None
        tts = riva.client.SpeechSynthesisService(_auth(fid))
        resp = tts.synthesize(
            text=text,
            voice_name=VOICE,
            language_code="en-US",
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hz=sample_rate_hz,
        )
        return resp.audio
    except Exception:
        return None
