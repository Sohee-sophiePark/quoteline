import { useState } from "react";
import { sentences } from "../lib/notebook";
import { foundBy, quotesVerified } from "../lib/run";
import type { Run } from "../types";

export default function ReviewLedger({ run }: { run: Run }) {
  const [open, setOpen] = useState<string | null>(null);
  const r = run.rendered;
  if (!r) return <p className="text-sm text-muted">No answer ({run.status}).</p>;
  const gates = run.gates.at(-1) ?? [];
  const verdict = run.verdicts.at(-1);
  const refs = Object.fromEntries(r.references.map((x) => [String(x.n), x]));
  const via = foundBy(run);
  const verified = quotesVerified(run);
  const rows = [r.takeaway, ...r.paragraphs].flatMap((p, si) => sentences(p).map((s, i) => ({ s, k: `${si}:${i}` })));

  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5" aria-labelledby="review-h">
      <h3 id="review-h" className="mb-2 text-lg font-semibold text-ink">{run.question}</h3>
      <dl className="mb-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {[
          ["Code checks", `${gates.filter((g) => g.passed).length}/${gates.length} passed`],
          ["Faithfulness", verdict ? `${verdict.faithfulness}/5` : "—"],
          ["Coverage", verdict ? `${verdict.coverage}/5` : "—"],
          ["Effort", `${run.drafts.length - 1} rev · ${run.llm_calls} calls`],
        ].map(([k, v]) => (
          <div key={k} className="rounded-md bg-accent-soft px-3 py-2">
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="font-mono text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <ol className="flex flex-col divide-y divide-line">
        {rows.map(({ s, k }) => {
          const cites = [...new Set(s.match(/\[\d+\]/g) ?? [])].map((c) => c.slice(1, -1));
          return (
            <li key={k} className="py-3">
              <p className="text-ink">{s.replace(/\s*\[\d+\]/g, "")}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {cites.length === 0 && <span className="font-mono text-xs text-red-700">no citation</span>}
                {cites.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setOpen(open === `${k}-${n}` ? null : `${k}-${n}`)}
                    aria-expanded={open === `${k}-${n}`}
                    className="rounded border border-accent px-1.5 font-mono text-xs text-accent hover:bg-accent-soft"
                  >
                    [{n}] evidence
                  </button>
                ))}
              </div>
              {cites
                .filter((n) => open === `${k}-${n}` && refs[n])
                .map((n) => (
                  <div key={n} className="mt-2 border-l-2 border-accent pl-3 text-sm">
                    <a href={refs[n].url} className="text-accent underline" rel="noopener noreferrer" target="_blank">
                      {refs[n].title}
                    </a>{" "}
                    <span className="text-muted">— {refs[n].authors}, {refs[n].year}</span>
                    {refs[n].contribution_quote && (
                      <p className="mt-1 text-ink">
                        <mark className="bg-mark px-0.5 text-ink">{refs[n].contribution_quote}</mark>
                        {verified && <span className="ml-2 font-mono text-xs text-accent">✓ exact in abstract</span>}
                      </p>
                    )}
                    <p className="mt-1 font-mono text-xs text-muted">found by {(via[refs[n].id] ?? []).join(" · ") || "—"}</p>
                  </div>
                ))}
            </li>
          );
        })}
      </ol>
    </article>
  );
}
