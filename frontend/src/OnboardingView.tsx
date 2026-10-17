import { useEffect, useState } from "react";
import { api } from "./api";
import type { OnboardingQuestion } from "./types";

// Dealer setup as a short wizard: one multiple-choice question per screen, with a recommended default.
// Answers stay on this screen until the backend stores them.
export default function OnboardingView() {
  const [questions, setQuestions] = useState<OnboardingQuestion[]>([]);
  const [offline, setOffline] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [done, setDone] = useState(false);

  useEffect(() => {
    api.onboardingQuestions().then((r) => {
      setQuestions(r.data);
      setOffline(r.offline);
      setLoaded(true);
    });
  }, []);

  if (!loaded) return <p className="muted">Loading setup…</p>;
  if (offline || questions.length === 0) {
    return <p className="notice danger">Setup is unavailable right now. Try again in a moment.</p>;
  }

  if (done) {
    return (
      <section className="done" aria-live="polite">
        <h2>You're set up</h2>
        <p>The team will use these choices from now on. You can change them any time.</p>
        <button onClick={() => { setStep(0); setDone(false); }}>Review my answers</button>
      </section>
    );
  }

  const q = questions[step];
  const picked = answers[q.id] ?? [];
  const isLast = step === questions.length - 1;
  const progress = (step / questions.length) * 100;

  const choose = (value: string) => {
    setAnswers((a) => {
      const current = a[q.id] ?? [];
      if (q.type === "single") return { ...a, [q.id]: [value] };
      return { ...a, [q.id]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value] };
    });
  };

  // A default is pre-selected so the dealer can press Next without thinking about it.
  const useRecommended = () => {
    setAnswers((a) => ({ ...a, [q.id]: q.options.filter((o) => o.recommended).map((o) => o.value) }));
  };

  const next = () => {
    if (!picked.length) return;
    if (isLast) setDone(true);
    else setStep(step + 1);
  };

  return (
    <section className="wizard" aria-labelledby="q-title">
      <div className="wizard-top">
        <span className="muted small">Question {step + 1} of {questions.length}</span>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} aria-label="Setup progress">
          <div style={{ width: `${progress}%` }} />
        </div>
      </div>

      <h2 id="q-title" className="wizard-q">{q.ask}</h2>
      <p className="muted small">{q.type === "multi" ? "Pick all that apply." : "Pick one."}</p>

      <div className="options" role={q.type === "single" ? "radiogroup" : "group"} aria-label={q.ask}>
        {q.options.map((o) => {
          const on = picked.includes(o.value);
          return (
            <button
              key={o.value}
              className={`option ${on ? "on" : ""}`}
              aria-pressed={on}
              onClick={() => choose(o.value)}
            >
              <span className="tick" aria-hidden="true">{on ? "✓" : ""}</span>
              <span>{o.label}</span>
              {o.recommended && <span className="pill">Most dealers pick this</span>}
            </button>
          );
        })}
      </div>

      <div className="wizard-nav">
        <button className="quiet" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Back</button>
        <div className="row">
          <button className="quiet" onClick={useRecommended}>Use recommended</button>
          <button className="primary" onClick={next} disabled={!picked.length}>
            {isLast ? "Finish setup" : "Next"}
          </button>
        </div>
      </div>
    </section>
  );
}
