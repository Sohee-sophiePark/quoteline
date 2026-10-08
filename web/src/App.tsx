import { useEffect, useState } from "react";
import Ask from "./components/Ask";
import FeedView from "./components/FeedView";
import Policy from "./components/Policy";
import { isStatic, loadFeed, loadStatic } from "./data";
import type { Feed, StaticData } from "./types";

const TABS = ["Ask", "Daily feed", "Policy lab"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [tab, setTab] = useState<Tab>("Ask");
  const [data, setData] = useState<StaticData | null>(null);
  const [feed, setFeed] = useState<Feed | null>(null);

  useEffect(() => {
    loadStatic().then(setData);
    loadFeed().then(setFeed);
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold text-slate-900">Quoteline</h1>
        <p className="mt-1 text-sm text-slate-600">
          Cited answers about AI/ML research. Every citation is checked by code against a paper the agent fetched.
        </p>
      </header>
      {isStatic && (
        <p role="note" className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Demo: answers are recorded runs replayed in your browser, with no live model calls. Paper metadata comes
          from arXiv (CC0), Hugging Face and OpenAlex (CC0), each with its date.
        </p>
      )}
      <nav aria-label="Sections" className="mb-6 flex flex-wrap gap-2 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            aria-current={tab === t ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t ? "border-emerald-700 text-emerald-800" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>
      <main>
        {tab === "Ask" && <Ask replays={data?.replays ?? []} />}
        {tab === "Daily feed" && <FeedView feed={feed} />}
        {tab === "Policy lab" && <Policy bandit={data?.bandit ?? null} />}
      </main>
      <footer className="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-600">
        Search results partly from OpenAlex. Abstracts are arXiv metadata (CC0); links go to arXiv.
      </footer>
    </div>
  );
}
