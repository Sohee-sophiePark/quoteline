import type { Feed, Paper } from "../types";

function Card({ p }: { p: Paper }) {
  const authors = p.authors.length > 1 ? `${p.authors[0]} et al.` : p.authors[0] ?? "";
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-3">
      <a
        href={p.url ?? `https://arxiv.org/abs/${p.id}`}
        className="font-medium text-emerald-800 underline"
        rel="noopener noreferrer"
        target="_blank"
      >
        {p.title}
      </a>
      <p className="mt-1 text-xs text-slate-600">
        {authors} · {p.published} · {p.categories.slice(0, 2).join(", ")}
        {p.upvotes ? ` · ${p.upvotes} upvotes` : ""}
      </p>
      <details className="mt-1 text-sm text-slate-700">
        <summary className="cursor-pointer text-xs text-slate-600">Abstract</summary>
        <p className="mt-1 leading-relaxed">{p.abstract}</p>
      </details>
    </li>
  );
}

export default function FeedView({ feed }: { feed: Feed | null }) {
  if (!feed) return <p className="text-sm text-slate-600">Feed not available yet.</p>;
  return (
    <section aria-labelledby="feed-h">
      <h2 id="feed-h" className="sr-only">Daily feed</h2>
      <p className="mb-4 text-sm text-slate-600">
        Updated {feed.generated}. Ranked by code: Trending = log-scaled upvotes with a 3-day half-life; New on arXiv =
        newest first.
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 font-semibold text-slate-900">Trending</h3>
          <ul className="flex flex-col gap-2">
            {feed.trending.map((p) => (
              <Card key={p.id} p={p} />
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 font-semibold text-slate-900">New on arXiv</h3>
          <ul className="flex flex-col gap-2">
            {feed.new.map((p) => (
              <Card key={p.id} p={p} />
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
