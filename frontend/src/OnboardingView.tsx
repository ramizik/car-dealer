import { useEffect, useState } from "react";
import { api } from "./api";
import type { OnboardingQuestion } from "./types";

// Dealer setup: the questions the onboarding agent asks. Answers stay in this browser tab until the brain stores them.
export default function OnboardingView() {
  const [questions, setQuestions] = useState<OnboardingQuestion[]>([]);
  const [offline, setOffline] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    api.onboardingQuestions().then((r) => {
      setQuestions(r.data);
      setOffline(r.offline);
    });
  }, []);

  if (offline) return <p className="muted">Dealer setup is unavailable while the backend is offline.</p>;

  return (
    <section className="onboarding">
      <h2>Dealer setup</h2>
      <p className="muted small">Answer each question. Nothing is listed or bid until you say YES to authority.</p>
      {questions.map((q, i) => (
        <label key={q.id} className="card">
          <span className="car">
            {i + 1}. {q.ask}
          </span>
          <textarea
            rows={2}
            value={answers[q.id] ?? ""}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
          />
        </label>
      ))}
    </section>
  );
}
