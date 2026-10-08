import { useState } from "react";
import { approveLive, askLive, isStatic } from "../data";
import type { Run } from "../types";
import Answer from "./Answer";
import Trace from "./Trace";

export default function Ask({ replays }: { replays: Run[] }) {
  const [run, setRun] = useState<Run | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      setRun(await askLive(question));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="ask-h">
      <h2 id="ask-h" className="sr-only">Ask</h2>
      {!isStatic && (
        <form
          className="mb-4 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label htmlFor="q" className="sr-only">Research question</label>
          <input
            id="q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            minLength={8}
            maxLength={300}
            placeholder="Ask about AI/ML research…"
            className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
          />
          <button
            disabled={busy || question.length < 8}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:bg-slate-400"
          >
            {busy ? "Researching…" : "Ask (live)"}
          </button>
        </form>
      )}
      {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
      {replays.length > 0 ? (
        <div className="mb-6">
          <p className="mb-2 text-sm text-slate-600">Recorded questions:</p>
          <ul className="flex flex-col gap-2">
            {replays.map((r) => (
              <li key={r.run_id}>
                <button
                  onClick={() => setRun(r)}
                  aria-pressed={run?.run_id === r.run_id}
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    run?.run_id === r.run_id ? "border-emerald-700 bg-emerald-50" : "border-slate-300 bg-white hover:border-slate-500"
                  }`}
                >
                  {r.question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        isStatic && <p className="text-sm text-slate-600">No recorded runs yet.</p>
      )}
      {run && (
        <>
          <Answer run={run} />
          {!isStatic && (run.status === "AWAITING_APPROVAL" || run.status === "NEEDS_REVIEW") && (
            <button
              onClick={async () => setRun(await approveLive(run.run_id))}
              className="mt-3 rounded-md border border-emerald-700 px-4 py-2 text-sm font-medium text-emerald-800"
            >
              Approve and save to library
            </button>
          )}
          <Trace run={run} />
        </>
      )}
    </section>
  );
}
