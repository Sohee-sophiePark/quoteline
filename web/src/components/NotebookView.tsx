import { download, type Notebook } from "../lib/notebook";
import { Cited } from "./Answer";

type Props = { nb: Notebook; onRemove: (runId: string) => void; onClear: () => void };

export default function NotebookView({ nb, onRemove, onClear }: Props) {
  return (
    <section aria-labelledby="nb-h">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h2 id="nb-h" className="mr-auto text-lg font-semibold text-ink">Notebook</h2>
        <button
          type="button"
          onClick={() => download(nb)}
          disabled={nb.entries.length === 0}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:bg-muted"
        >
          Download .md
        </button>
        <button
          type="button"
          onClick={() => window.confirm("Clear all saved answers, highlights and notes?") && onClear()}
          disabled={nb.entries.length === 0 && Object.keys(nb.marks).length === 0}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink disabled:text-muted"
        >
          Clear
        </button>
      </div>
      <p className="mb-4 text-sm text-muted">
        Saved in this browser only — nothing is sent anywhere. Download to keep a copy.
      </p>
      {nb.entries.length === 0 && <p className="text-sm text-muted">No saved answers yet. Use "Save to notebook" on an answer.</p>}
      <ul className="flex flex-col gap-3">
        {nb.entries.map((e) => {
          const marks = Object.values(nb.marks[e.runId] ?? {});
          return (
            <li key={e.runId} className="rounded-lg border border-line bg-white p-4">
              <div className="flex items-start gap-2">
                <h3 className="mr-auto font-semibold text-ink">{e.question}</h3>
                <button type="button" onClick={() => onRemove(e.runId)} className="text-sm text-muted underline">
                  Remove
                </button>
              </div>
              <p className="mt-1 text-sm text-ink">
                <Cited text={e.takeaway} />
              </p>
              {marks.map((m) => (
                <div key={m.text} className="mt-2 border-l-2 border-accent bg-accent-soft px-2 py-1 text-sm">
                  <p className="text-ink">
                    <Cited text={m.text} />
                  </p>
                  {m.note && <p className="text-muted">✎ {m.note}</p>}
                </div>
              ))}
              <p className="mt-2 font-mono text-xs text-muted">
                {e.references.length} references · saved {e.savedAt}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
