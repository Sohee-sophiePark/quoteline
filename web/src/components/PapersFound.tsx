import { foundBy } from "../lib/run";
import type { Run } from "../types";

export default function PapersFound({ run }: { run: Run }) {
  const via = foundBy(run);
  const cited = new Set(run.rendered?.references.map((r) => r.id) ?? []);
  const papers = Object.values(run.papers);
  return (
    <details className="mt-4 rounded-lg border border-line bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-ink">
        Papers found ({papers.length}, {cited.size} cited)
      </summary>
      <ul className="mt-3 flex flex-col gap-2 text-sm">
        {papers.map((p) => (
          <li key={p.id} className="break-words">
            <a href={`https://arxiv.org/abs/${p.id}`} className="text-accent underline" rel="noopener noreferrer" target="_blank">
              {p.title}
            </a>{" "}
            <span className="text-muted">
              — {p.authors.length > 1 ? `${p.authors[0]} et al.` : p.authors[0] ?? ""}, {p.published.slice(0, 4)}
            </span>
            <div className="font-mono text-xs text-muted">
              {cited.has(p.id) && <span className="mr-2 text-accent">cited</span>}
              {(via[p.id] ?? []).join(" · ")}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
