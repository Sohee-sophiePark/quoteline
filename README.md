# Quoteline

Cited answers about AI/ML research, where every citation is checked by code against a paper the agent actually
fetched — plus a contextual bandit that learns which source to search, and a daily paper feed.

**Live demo:** https://sohee-sophiepark.github.io/quoteline/ (recorded runs replayed in the browser, no API key needed).

## The problem

LLM research assistants invent papers, misquote abstracts and spend many calls searching sources that rarely help.
This project makes three things verifiable:

1. **Citations** — the model cites only through `{{p:<arXiv id>}}` placeholders; code checks that each cited paper was
   fetched, that each quoted contribution appears verbatim in its abstract, and that every sentence is cited. Titles,
   authors and years are rendered from metadata, never written by the model.
2. **Source choice** — a contextual bandit (LinUCB) picks the search source and query style per question; its gain over
   the best single source is measured on held-out questions with a confidence interval.
3. **Freshness** — a daily job ranks new papers by code, with no LLM and no secrets.

## Architecture

```
Question ─► Planner (LLM) ─► sub-questions
               │
               ▼
        Source policy (LinUCB, code features) ─► 2 of 9 arms per sub-question
               │
               ▼
   arXiv API · Hugging Face papers · OpenAlex   (parallel, read-only, polite rate limits)
               │
               ▼
   Canonical text from arXiv (CC0) ─► Reader (LLM): exact quotes + claims
               │
               ▼
   Writer (LLM, the only writer) ─► Gates G1–G5 (code) ─► Evaluator (LLM, separate)
               ▲                         │ fail               │ score < 4
               └──────── revise (max 2) ◄┴────────────────────┘
               │ pass
               ▼
   Rendered answer + references ─► human approval ─► saved report
```

Daily feed: arXiv RSS (cs.AI, cs.CL, cs.LG) + Hugging Face daily papers → merged by arXiv ID → **Trending**
(log-scaled upvotes with a 3-day half-life) and **New on arXiv** (newest first) → static JSON on Pages.

## Capabilities by module

| Module | What it does |
|---|---|
| `sources/` | arXiv Atom/RSS, Hugging Face JSON and OpenAlex parsers; one polite HTTP client (per-host spacing, server wait hints, retries); merge by arXiv ID with arXiv text winning |
| `orchestrator.py` | The research flow above; checkpoints after every step, `resume` after a stop, approval as the only action |
| `gates.py`, `render.py` | G1 citations resolve · G2 quotes exact · G3 every sentence cited · G4 no model-written metadata · G5 untrusted-content flags; numbered references from metadata |
| `bandit.py` | Context features, disjoint LinUCB, full-information replay evaluation, bootstrap comparison with baselines |
| `dataset.py` | Known-item training questions from papers sampled across 2023–2026, all-arm recording, golden relevance judging |
| `feed.py` | The daily feed ranking |
| `harness.py`, `llm/` | Hand-built LLM runner: rate limiter, retries, model fallback, record/replay cassettes, trace |
| `api.py`, `web/` | Local live mode (127.0.0.1) and the static demo: Ask · Daily feed · Policy lab |

## Run it

```bash
make setup            # uv sync + npm ci
make test lint eval   # offline: tests, lint, tier-2 evals on recorded runs
make build-static     # the public demo build in web/dist
```

Live mode (free-tier keys exported in your shell, never read from files):

```bash
export GEMINI_API_KEY=...          # Google AI Studio, free tier
export OPENALEX_API_KEY=...        # optional, raises the OpenAlex daily budget
make smoke                         # lists available Gemini models
make dev                           # API on 127.0.0.1:8010 + web on localhost:5173
make dataset                       # training questions, all-arm recording, judgments, policy report
make record                        # record demo runs for the public site, then re-check them offline
```

## Evaluation

| Tier | What | Key |
|---|---|---|
| 1 | Unit tests on real API fixtures: parsers, rate limiting, gates, renderer, bandit math, orchestrator paths, API | No |
| 2 | Recorded runs re-run from cassettes and must match; citations resolve; quotes exact; expected paper retrieved and cited; policy report | No |
| 3 | The same metrics on fresh live runs | Yes |

## Data and licences

Paper metadata from arXiv (CC0) and OpenAlex (CC0); Hugging Face daily papers for upvotes. Displayed text is always
arXiv metadata, linked to arXiv. See `data/README.md`.

## Credits

Built with [Claude Code](https://claude.ai/claude-code).
