import { useState } from "react";
import { type Mark, sentences } from "../lib/notebook";
import { quotesVerified } from "../lib/run";
import type { Run } from "../types";

const STATUS: Record<string, string> = {
  AWAITING_APPROVAL: "Passed checks · awaiting approval",
  NEEDS_REVIEW: "Needs review",
  APPROVED: "Approved",
};

export function Cited({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[\d+\])/).map((part, i) =>
        /^\[\d+\]$/.test(part) ? (
          <span key={i} className="font-mono text-sm text-accent">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  );
}

type Props = { run: Run; marks: Record<string, Mark>; onMark: (key: string, mark: Mark | null) => void };

export default function Answer({ run, marks, onMark }: Props) {
  const [active, setActive] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const r = run.rendered;
  if (!r) return <p className="text-sm text-muted">No answer ({run.status}).</p>;
  const sections = [r.takeaway, ...r.paragraphs];
  const verified = quotesVerified(run);

  const select = (k: string) => {
    setActive(active === k ? null : k);
    setDraft(marks[k]?.note ?? "");
  };

  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5" aria-labelledby="answer-h">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-accent-soft px-2 py-0.5 text-ink">{STATUS[run.status] ?? run.status}</span>
        <span className="text-muted">
          {run.llm_calls} LLM calls · {run.drafts.length - 1} revision{run.drafts.length === 2 ? "" : "s"}
        </span>
      </div>
      <h3 id="answer-h" className="mb-1 text-lg font-semibold text-ink">{run.question}</h3>
      <p className="mb-3 text-xs text-muted">
        Select a sentence to highlight it or add a note. <mark className="bg-mark px-0.5 text-ink">Yellow</mark> = verbatim
        from the paper · <span className="border-l-2 border-accent bg-accent-soft px-1 text-ink">Lavender</span> = your
        highlights.
      </p>
      {sections.map((section, si) => {
        const keys = sentences(section).map((s, i) => ({ s, k: `${si}:${i}` }));
        const notes = keys.filter(({ k }) => marks[k]?.note);
        return (
          <div key={si} className="mb-3">
            <p className={`leading-relaxed text-ink ${si === 0 ? "font-medium" : ""}`}>
              {keys.map(({ s, k }) => (
                <span key={k}>
                  <button
                    type="button"
                    onClick={() => select(k)}
                    aria-expanded={active === k}
                    aria-label={`${marks[k] ? "Highlighted: " : ""}${s}`}
                    className={`inline rounded-sm text-left hover:bg-zinc-100 ${
                      marks[k] ? "border-l-2 border-accent bg-accent-soft pl-1" : ""
                    } ${active === k ? "ring-2 ring-accent/40" : ""}`}
                  >
                    <Cited text={s} />
                  </button>{" "}
                </span>
              ))}
            </p>
            {notes.map(({ k }) => (
              <p key={k} className="mt-1 border-l-2 border-accent pl-2 text-sm text-muted">
                ✎ {marks[k].note}
              </p>
            ))}
            {keys.some(({ k }) => k === active) && active && (
              <div role="group" aria-label="Sentence actions" className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-line p-2 text-sm">
                <button
                  type="button"
                  onClick={() => onMark(active, marks[active] ? null : { text: keys.find((x) => x.k === active)!.s, note: "" })}
                  className="rounded-md border border-accent px-3 py-1 text-accent hover:bg-accent-soft"
                >
                  {marks[active] ? "Remove highlight" : "Highlight"}
                </button>
                <label htmlFor="note" className="sr-only">Note</label>
                <input
                  id="note"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  maxLength={500}
                  placeholder="Add a note…"
                  className="min-w-0 flex-1 rounded-md border border-line px-2 py-1"
                />
                <button
                  type="button"
                  onClick={() => {
                    onMark(active, { text: keys.find((x) => x.k === active)!.s, note: draft.trim() });
                    setActive(null);
                  }}
                  className="rounded-md bg-accent px-3 py-1 text-white"
                >
                  Save note
                </button>
              </div>
            )}
          </div>
        );
      })}
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
                {verified && <span className="ml-2 font-mono text-xs text-accent">✓ exact in abstract</span>}
              </p>
            )}
          </li>
        ))}
      </ol>
    </article>
  );
}
