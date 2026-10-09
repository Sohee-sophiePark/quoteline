import { useState } from "react";
import { approveLive, askLive, isStatic } from "../data";
import type { Mark } from "../lib/notebook";
import type { Run } from "../types";
import Answer from "./Answer";
import PapersFound from "./PapersFound";
import ReviewLedger from "./ReviewLedger";
import Trace from "./Trace";

type Props = {
  replays: Run[];
  marks: Record<string, Record<string, Mark>>;
  saved: Set<string>;
  onMark: (runId: string, key: string, mark: Mark | null) => void;
  onSave: (run: Run) => void;
  onRemove: (runId: string) => void;
};

export default function Ask({ replays, marks, saved, onMark, onSave, onRemove }: Props) {
  const [run, setRun] = useState<Run | null>(null);
  const [mode, setMode] = useState<"read" | "review">("read");
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
            className="min-w-0 flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm"
          />
          <button
            disabled={busy || question.length < 8}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:bg-muted"
          >
            {busy ? "Researching…" : "Ask (live)"}
          </button>
        </form>
      )}
      {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
      {replays.length > 0 ? (
        <div className="mb-6">
          <p className="mb-2 text-sm text-muted">Recorded questions:</p>
          <ul className="flex flex-col gap-2">
            {replays.map((r) => (
              <li key={r.run_id}>
                <button
                  onClick={() => setRun(r)}
                  aria-pressed={run?.run_id === r.run_id}
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    run?.run_id === r.run_id ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-muted"
                  }`}
                >
                  {r.question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        isStatic && <p className="text-sm text-muted">No recorded runs yet.</p>
      )}
      {run && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div role="group" aria-label="View" className="inline-flex rounded-md border border-line p-0.5 text-sm">
              {(["read", "review"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                  className={`rounded px-3 py-1 ${mode === m ? "bg-accent text-white" : "text-ink hover:bg-accent-soft"}`}
                >
                  {m === "read" ? "Read" : "Review evidence"}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => (saved.has(run.run_id) ? onRemove(run.run_id) : onSave(run))}
              aria-pressed={saved.has(run.run_id)}
              className="ml-auto rounded-md border border-accent px-3 py-1 text-sm text-accent hover:bg-accent-soft"
            >
              {saved.has(run.run_id) ? "✓ Saved to notebook" : "Save to notebook"}
            </button>
          </div>
          {mode === "read" ? (
            <Answer run={run} marks={marks[run.run_id] ?? {}} onMark={(k, m) => onMark(run.run_id, k, m)} />
          ) : (
            <ReviewLedger run={run} />
          )}
          {!isStatic && (run.status === "AWAITING_APPROVAL" || run.status === "NEEDS_REVIEW") && (
            <button
              onClick={async () => setRun(await approveLive(run.run_id))}
              className="mt-3 rounded-md border border-accent px-4 py-2 text-sm font-medium text-accent"
            >
              Approve and save to library
            </button>
          )}
          <PapersFound run={run} />
          <Trace run={run} />
        </>
      )}
    </section>
  );
}
