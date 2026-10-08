import type { Run } from "../types";

export default function Trace({ run }: { run: Run }) {
  const gates = run.gates[run.gates.length - 1] ?? [];
  return (
    <details className="mt-4 rounded-lg border border-line bg-white p-4" open>
      <summary className="cursor-pointer text-sm font-semibold text-ink">How this answer was made</summary>
      <h4 className="mt-3 mb-1 text-sm font-semibold text-ink">Sources chosen by the policy</h4>
      <ul className="flex flex-col gap-2 text-sm">
        {run.choices.map((c) => (
          <li key={c.subquestion}>
            <span className="text-ink">{c.subquestion}</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {c.arms.map((a) => (
                <span key={a} className="rounded bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent">
                  {a} ({c.scores[a]?.toFixed(2)})
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <h4 className="mt-3 mb-1 text-sm font-semibold text-ink">Code checks on the final draft</h4>
      <ul className="text-sm">
        {gates.map((g) => (
          <li key={g.gate} className={g.passed ? "text-ink" : "text-red-700"}>
            <span aria-hidden>{g.passed ? "✓" : "✗"}</span> {g.gate}
            {g.details.length > 0 && <span className="text-muted"> — {g.details.join("; ")}</span>}
          </li>
        ))}
      </ul>
      <h4 className="mt-3 mb-1 text-sm font-semibold text-ink">Evaluator</h4>
      <ul className="text-sm text-ink">
        {run.verdicts.map((v, i) => (
          <li key={i}>
            Round {i + 1}: faithfulness {v.faithfulness}/5, coverage {v.coverage}/5
            {v.issues.length > 0 && <span className="text-muted"> — {v.issues.join("; ")}</span>}
          </li>
        ))}
      </ul>
      <h4 className="mt-3 mb-1 text-sm font-semibold text-ink">Steps</h4>
      <ol className="font-mono text-xs text-ink">
        {run.events
          .filter((e) => e.kind !== "llm_call")
          .map((e) => (
            <li key={e.seq} className={e.level === "warn" ? "text-accent" : ""}>
              {(e.t_ms / 1000).toFixed(1)}s {e.agent}: {e.kind}
              {e.kind === "step_done" ? ` ${String(e.payload.step)}` : ""}
            </li>
          ))}
      </ol>
    </details>
  );
}
