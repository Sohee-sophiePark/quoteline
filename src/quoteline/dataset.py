"""Bandit dataset: sample targets, generate known-item questions, record all arms, judge golden."""

import asyncio
import datetime as dt
import json
import random
from pathlib import Path

import numpy as np

from quoteline.bandit import features
from quoteline.gates import wrap
from quoteline.harness import Runner, prompt
from quoteline.models import ARMS, JudgmentBatch, KnownItemBatch, Paper
from quoteline.sources import arxiv
from quoteline.sources.http import PoliteHttp
from quoteline.sources.query import terms
from quoteline.sources.retrieve import canonical, merge, run_arm

STYLES = ["fact", "method", "survey"]
CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]


def read_jsonl(path: Path) -> list[dict]:
    return (
        [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        if path.exists()
        else []
    )


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)


def sample_dates(start: dt.date, end: dt.date, n: int) -> list[str]:
    """`n` weekdays spread evenly between `start` and `end`."""
    step = (end - start) / max(n - 1, 1)
    days = [start + step * i for i in range(n)]
    return [(d - dt.timedelta(days=max(0, d.weekday() - 4))).isoformat() for d in days]


async def sample_targets(
    http: PoliteHttp, dates: list[str], per_date: int, today: str, seed: int = 0
) -> list[Paper]:
    """Source-neutral targets: arXiv submissions per date, rotating cs.AI, cs.CL, cs.LG."""
    rng = random.Random(seed)
    out: list[Paper] = []
    for i, d in enumerate(dates):
        cat = CATEGORIES[i % len(CATEGORIES)]
        papers = [p for p in await arxiv.by_date(http, cat, d, 50, today) if p.abstract]
        out += rng.sample(papers, min(per_date, len(papers)))
    return merge(out)


def style_for(p: Paper, i: int, today: str) -> str:
    age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(p.published or today)).days
    return "recent" if age <= 180 and i % 2 == 0 else STYLES[i % 3]


def leaks_title(question: str, title: str) -> bool:
    """True when the question copies the title's distinctive name or most of its words."""
    q, t = set(terms(question, 50)), set(terms(title, 50))
    name = title.split(":")[0].strip().lower() if ":" in title else ""
    return (bool(name) and name in question.lower()) or (bool(t) and len(q & t) / len(t) > 0.5)


async def generate_questions(
    runner: Runner, targets: list[Paper], today: str, batch: int = 10
) -> list[dict]:
    rows = []
    for start in range(0, len(targets), batch):
        chunk = targets[start : start + batch]
        user = "\n".join(
            wrap("paper", f"{p.title}\n{p.abstract}", id=p.id, style=style_for(p, start + i, today))
            for i, p in enumerate(chunk)
        )
        out = await runner.call(
            "dataset", prompt(runner.settings, "questions"), user, KnownItemBatch
        )
        by_id = {p.id: p for p in chunk}
        for q in out.questions:
            p = by_id.pop(q.paper_id, None)  # one question per paper
            if p and not leaks_title(q.question, p.title):
                rows.append({"question": q.question, "target": q.paper_id})
    return rows


async def record_arms(
    http: PoliteHttp, question: str, k: int, today: str
) -> dict[str, list[Paper]]:
    results = await asyncio.gather(*(run_arm(http, a, question, k, today) for a in ARMS))
    return {a.name: r for a, r in zip(ARMS, results, strict=True)}


async def judge(runner: Runner, question: str, papers: list[Paper]) -> dict[str, bool]:
    user = f"{wrap('question', question)}\n\n" + "\n".join(
        wrap("paper", f"{p.title}\n{p.abstract}", id=p.id) for p in papers
    )
    out = await runner.call("dataset", prompt(runner.settings, "judge"), user, JudgmentBatch)
    return {j.paper_id: j.relevant for j in out.judgments if j.paper_id in {p.id for p in papers}}


async def golden_papers(http: PoliteHttp, rows: list[dict], today: str) -> list[Paper]:
    ids = list(dict.fromkeys(i for r in rows for ids in r["arms"].values() for i in ids))
    return await canonical(http, [Paper(id=i, title="") for i in ids], today)


def known_item_matrix(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """X = context features; R[q, a] = 1 if the target paper is in arm a's top-k."""
    X = np.stack([features(r["question"]) for r in rows])
    R = np.array([[float(r["target"] in r["arms"][a.name]) for a in ARMS] for r in rows])
    return X, R


def golden_matrix(
    rows: list[dict], judgments: dict[str, dict[str, bool]], k: int
) -> tuple[np.ndarray, np.ndarray]:
    """R[q, a] = judged-relevant papers in arm a's top-k ÷ k."""
    X = np.stack([features(r["question"]) for r in rows])
    R = np.array(
        [
            [sum(judgments[r["qid"]].get(i, False) for i in r["arms"][a.name]) / k for a in ARMS]
            for r in rows
        ]
    )
    return X, R
