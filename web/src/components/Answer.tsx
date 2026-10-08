import type { Run } from "../types";

const STATUS: Record<string, string> = {
  AWAITING_APPROVAL: "Passed checks · awaiting approval",
  NEEDS_REVIEW: "Needs review",
  APPROVED: "Approved",
};

export default function Answer({ run }: { run: Run }) {
  const r = run.rendered;
  if (!r) return <p className="text-sm text-slate-600">No answer ({run.status}).</p>;
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 sm:p-5" aria-labelledby="answer-h">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">{STATUS[run.status] ?? run.status}</span>
        <span className="text-slate-600">
          {run.llm_calls} LLM calls · {run.drafts.length - 1} revision{run.drafts.length === 2 ? "" : "s"}
        </span>
      </div>
      <h3 id="answer-h" className="mb-3 text-lg font-semibold text-slate-900">{run.question}</h3>
      <p className="mb-3 font-medium text-slate-900">{r.takeaway}</p>
      {r.paragraphs.map((p, i) => (
        <p key={i} className="mb-3 leading-relaxed text-slate-700">{p}</p>
      ))}
      <h4 className="mt-4 mb-2 text-sm font-semibold text-slate-900">References</h4>
      <ol className="flex flex-col gap-3 text-sm">
        {r.references.map((x) => (
          <li key={x.id} className="break-words">
            <span className="font-mono text-slate-600">[{x.n}]</span>{" "}
            <a href={x.url} className="text-emerald-800 underline" rel="noopener noreferrer" target="_blank">
              {x.title}
            </a>{" "}
            <span className="text-slate-600">— {x.authors}, {x.year}</span>
            {x.contribution_quote && (
              <blockquote className="mt-1 border-l-2 border-slate-300 pl-2 text-slate-700">
                Claimed contribution: “{x.contribution_quote}”
              </blockquote>
            )}
          </li>
        ))}
      </ol>
    </article>
  );
}
