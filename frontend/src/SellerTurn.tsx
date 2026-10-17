import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { money } from "./format";
import { startRecording, type Recording } from "./record";

type Props = { dealId: string; offer?: number };

// The seller's side of a live call: record the answer, check it, send it. Typing is always there as a fallback.
export default function SellerTurn({ dealId, offer }: Props) {
  const [mode, setMode] = useState<"idle" | "recording" | "review" | "sending">("idle");
  const [clip, setClip] = useState<Blob | null>(null);
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [secs, setSecs] = useState(0);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const rec = useRef<Recording | null>(null);
  const timer = useRef<number | null>(null);

  // Blob URLs for the preview player; revoke them so the browser does not keep old audio.
  useEffect(() => {
    if (!clip) return;
    const url = URL.createObjectURL(clip);
    setClipUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [clip]);

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  const start = async () => {
    setError("");
    try {
      rec.current = await startRecording();
    } catch {
      setError("Mic is blocked or missing. Type the seller's answer below.");
      return;
    }
    setSecs(0);
    setMode("recording");
    timer.current = window.setInterval(() => setSecs((s) => s + 1), 1000);
  };

  const stop = async () => {
    if (timer.current) window.clearInterval(timer.current);
    if (!rec.current) return setMode("idle");
    const blob = await rec.current.stop();
    rec.current = null;
    setClip(blob);
    setMode("review");
  };

  const sendAudio = async () => {
    if (!clip) return;
    setMode("sending");
    setError("");
    const r = await api.sendSellerAudio(dealId, clip);
    if (r.ok) return reset();
    setError(r.error ?? "Could not send. Try again or type it.");
    setMode("review");
  };

  const sendText = async () => {
    const text = typed.trim();
    if (!text) return;
    setMode("sending");
    setError("");
    const r = await api.sendSellerText(dealId, text);
    if (r.ok) return reset();
    setError(r.error ?? "Could not send. Try again.");
    setMode("idle");
  };

  const reset = () => {
    setClip(null);
    setTyped("");
    setMode("idle");
  };

  const busy = mode === "sending";

  return (
    <section className="seller-turn" aria-labelledby="seller-turn-title">
      <h3 id="seller-turn-title">Your turn: the seller answers</h3>
      <p className="small">
        {offer ? <>We offered <strong>{money(offer)}</strong>. </> : null}
        Ask the seller, then record their answer. Say a price, yes, or no.
      </p>

      {mode === "idle" && (
        <button className="primary big-mic" onClick={start} disabled={busy}>● Record seller's answer</button>
      )}
      {mode === "recording" && (
        <button className="danger big-mic" onClick={stop} aria-live="polite">
          ■ Stop ({secs}s)
        </button>
      )}
      {mode === "review" && clipUrl && (
        <div className="stack-sm">
          <audio controls src={clipUrl} />
          <div className="actions">
            <button onClick={start} disabled={busy}>Re-record</button>
            <button className="primary" onClick={sendAudio} disabled={busy}>Send answer</button>
          </div>
        </div>
      )}
      {mode === "sending" && <p className="small" role="status">Listening to the answer…</p>}

      <form className="row" onSubmit={(e) => { e.preventDefault(); void sendText(); }}>
        <label className="sr-only" htmlFor={`typed-${dealId}`}>Type the seller&apos;s answer</label>
        <input
          id={`typed-${dealId}`}
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="Or type what they said, e.g. 'Deal at 8,500'"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !typed.trim()}>Send text</button>
      </form>

      {error && <p className="notice danger" role="alert">{error}</p>}
    </section>
  );
}
