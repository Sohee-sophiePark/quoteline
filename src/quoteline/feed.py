"""Daily feed: arXiv category RSS + Hugging Face daily papers, merged by ID, ranked by code."""

import datetime as dt
import math

import httpx

from quoteline.config import FeedCfg
from quoteline.models import Paper
from quoteline.sources import arxiv, hf
from quoteline.sources.http import PoliteHttp
from quoteline.sources.retrieve import canonical, merge


def age_days(p: Paper, today: str) -> int:
    return max(0, (dt.date.fromisoformat(today) - dt.date.fromisoformat(p.published or today)).days)


def rank_trending(
    papers: list[Paper], today: str, half_life: float, n: int
) -> list[tuple[Paper, float]]:
    """Log-scaled upvotes (relative to the top paper) × 0.5^(age / half_life)."""
    voted = [p for p in papers if p.upvotes]
    top = max((p.upvotes for p in voted), default=0)
    scored = [
        (p, math.log1p(p.upvotes) / math.log1p(top) * 0.5 ** (age_days(p, today) / half_life))
        for p in voted
    ]
    return sorted(scored, key=lambda x: (-x[1], x[0].id))[:n]


def rank_new(papers: list[Paper], n: int, exclude: set[str]) -> list[Paper]:
    fresh = [p for p in papers if "arxiv" in p.sources and p.id not in exclude]
    return sorted(fresh, key=lambda p: (p.published, p.id), reverse=True)[:n]


def card(p: Paper, score: float | None = None) -> dict:
    out = p.model_dump(exclude={"fetched"}) | {"url": p.url}
    return out | ({"score": round(score, 4)} if score is not None else {})


async def build(http: PoliteHttp, cfg: FeedCfg, today: str) -> dict:
    papers: list[Paper] = []
    for cat in cfg.categories:
        papers += await arxiv.rss(http, cat, today)
    start = dt.date.fromisoformat(today)
    for i in range(cfg.window_days):
        papers += await hf.daily(http, (start - dt.timedelta(days=i)).isoformat(), today)
    merged = merge(papers)
    trending = rank_trending(merged, today, cfg.half_life_days, cfg.trending_size)
    try:
        canon = {p.id: p for p in await canonical(http, [p for p, _ in trending], today)}
    except httpx.HTTPStatusError:  # arXiv refused: keep Hugging Face's copy of the arXiv abstract
        canon = {}
    trending = [(canon.get(p.id, p), s) for p, s in trending]
    new = rank_new(merged, cfg.new_size, {p.id for p, _ in trending})
    return {
        "generated": today,
        "window_days": cfg.window_days,
        "sources": ["arXiv RSS (CC0 metadata)", "Hugging Face daily papers"],
        "trending": [card(p, s) for p, s in trending],
        "new": [card(p) for p in new],
    }
