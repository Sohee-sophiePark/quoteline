import type { Run } from "../types";

const STATUS: Record<string, string> = {
  AWAITING_APPROVAL: "Passed checks · awaiting approval",
  NEEDS_REVIEW: "Needs review",
  APPROVED: "Approved",
};

function Cited({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[\d+\])/).map((part, i) =>
        /^\[\d+\]$/.test(part) ? (
          <a key={i} href={`#ref-${part.slice(1, -1)}`} className="font-mono text-sm text-accent no-underline">
            {part}
          </a>
        ) : (
          part
        ),
      )}
    </>
  );
}

export default function Answer({ run }: { run: Run }) {
  const r = run.rendered;
  if (!r) return <p className="text-sm text-muted">No answer ({run.status}).</p>;
  const quotesVerified = run.gates.at(-1)?.find((g) => g.gate.startsWith("G2"))?.passed ?? false;
  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5" aria-labelledby="answer-h">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-accent-soft px-2 py-0.5 text-ink">{STATUS[run.status] ?? run.status}</span>
        <span className="text-muted">
          {run.llm_calls} LLM calls · {run.drafts.length - 1} revision{run.drafts.length === 2 ? "" : "s"}
        </span>
      </div>
      <h3 id="answer-h" className="mb-3 text-lg font-semibold text-ink">{run.question}</h3>
      <p className="mb-3 font-medium text-ink">
        <Cited text={r.takeaway} />
      </p>
      {r.paragraphs.map((p, i) => (
        <p key={i} className="mb-3 leading-relaxed text-ink">
          <Cited text={p} />
        </p>
      ))}
      <h4 className="mt-4 mb-2 text-sm font-semibold text-ink">References</h4>
      <ol className="flex flex-col gap-3 border-l-2 border-accent pl-3 text-sm">
        {r.references.map((x) => (
          <li key={x.id} id={`ref-${x.n}`} className="break-words">
            <span className="font-mono text-accent">[{x.n}]</span>{" "}
            <a href={x.url} className="text-accent underline" rel="noopener noreferrer" target="_blank">
              {x.title}
            </a>{" "}
            <span className="text-muted">— {x.authors}, {x.year}</span>
            {x.contribution_quote && (
              <p className="mt-1 text-ink">
                Claimed contribution: <mark className="bg-mark px-0.5 text-ink">{x.contribution_quote}</mark>
                {quotesVerified && <span className="ml-2 font-mono text-xs text-accent">✓ exact in abstract</span>}
              </p>
            )}
          </li>
        ))}
      </ol>
    </article>
  );
}
