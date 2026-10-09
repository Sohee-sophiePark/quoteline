import { useEffect, useState } from "react";
import type { Reference, Run } from "../types";

export type Mark = { text: string; note: string };
export type Entry = {
  runId: string;
  question: string;
  takeaway: string;
  paragraphs: string[];
  references: Reference[];
  savedAt: string;
};
export type Notebook = { marks: Record<string, Record<string, Mark>>; entries: Entry[] };

const KEY = "quoteline.notebook.v1";
const EMPTY: Notebook = { marks: {}, entries: [] };

export function sentences(text: string): string[] {
  return text.split(/(?<=[.!?])\s+(?=[A-Z[])/).filter((s) => s.trim());
}

function load(): Notebook {
  try {
    return { ...EMPTY, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
  } catch {
    return EMPTY;
  }
}

export function useNotebook() {
  const [nb, setNb] = useState<Notebook>(load);
  useEffect(() => localStorage.setItem(KEY, JSON.stringify(nb)), [nb]);

  const setMark = (runId: string, key: string, mark: Mark | null) =>
    setNb((s) => {
      const run = { ...(s.marks[runId] ?? {}) };
      if (mark) run[key] = mark;
      else delete run[key];
      return { ...s, marks: { ...s.marks, [runId]: run } };
    });

  const save = (run: Run) =>
    run.rendered &&
    setNb((s) => ({
      ...s,
      entries: [
        ...s.entries.filter((e) => e.runId !== run.run_id),
        {
          runId: run.run_id,
          question: run.question,
          takeaway: run.rendered!.takeaway,
          paragraphs: run.rendered!.paragraphs,
          references: run.rendered!.references,
          savedAt: new Date().toISOString().slice(0, 10),
        },
      ],
    }));

  const remove = (runId: string) => setNb((s) => ({ ...s, entries: s.entries.filter((e) => e.runId !== runId) }));
  const clear = () => setNb(EMPTY);
  return { nb, setMark, save, remove, clear };
}

const esc = (t: string) => t.replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function toMarkdown(nb: Notebook): string {
  const out = [
    "# Quoteline notebook",
    "",
    `Exported ${new Date().toISOString().slice(0, 10)}. Quotes are verbatim from arXiv abstracts (CC0).`,
  ];
  for (const e of nb.entries) {
    out.push("", `## ${esc(e.question)}`, "", `**${esc(e.takeaway)}**`, "", ...e.paragraphs.flatMap((p) => [esc(p), ""]));
    const marks = Object.values(nb.marks[e.runId] ?? {});
    if (marks.length) {
      out.push("### My highlights", "");
      for (const m of marks) out.push(`> ${esc(m.text)}`, ...(m.note ? ["", `Note: ${esc(m.note)}`] : []), "");
    }
    out.push("### References", "");
    for (const r of e.references) {
      out.push(`${r.n}. ${esc(r.title)} — ${esc(r.authors)}, ${r.year}. ${r.url}`);
      if (r.contribution_quote) out.push(`   Claimed contribution: "${esc(r.contribution_quote)}"`);
    }
    out.push("", `_Saved ${e.savedAt}_`);
  }
  return out.join("\n") + "\n";
}

export function download(nb: Notebook): void {
  const url = URL.createObjectURL(new Blob([toMarkdown(nb)], { type: "text/markdown" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: "quoteline-notebook.md" });
  a.click();
  URL.revokeObjectURL(url);
}
