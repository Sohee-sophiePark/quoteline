"""Run one arm (source × style), merge duplicates by arXiv ID, fill canonical text from arXiv."""

from quoteline.models import Arm, Paper
from quoteline.sources import arxiv, hf, openalex
from quoteline.sources.http import PoliteHttp

SEARCH = {"arxiv": arxiv.search, "hf": hf.search, "openalex": openalex.search}


async def run_arm(http: PoliteHttp, arm: Arm, text: str, k: int, fetched: str) -> list[Paper]:
    return await SEARCH[arm.source](http, text, arm.style, k, fetched)


def merge(papers: list[Paper]) -> list[Paper]:
    """One record per ID, first-seen order: arXiv text wins, upvotes kept, sources unioned."""
    out: dict[str, Paper] = {}
    for p in papers:
        if p.id not in out:
            out[p.id] = p.model_copy()
            continue
        cur = out[p.id]
        base, other = (p, cur) if "arxiv" in p.sources and "arxiv" not in cur.sources else (cur, p)
        out[p.id] = base.model_copy(
            update={
                "upvotes": cur.upvotes if cur.upvotes is not None else p.upvotes,
                "sources": list(dict.fromkeys(cur.sources + p.sources)),
                "abstract": base.abstract or other.abstract,
                "authors": base.authors or other.authors,
                "categories": base.categories or other.categories,
            }
        )
    return list(out.values())


async def canonical(http: PoliteHttp, papers: list[Paper], fetched: str) -> list[Paper]:
    """Replace each paper's text with arXiv's CC0 metadata; drops IDs arXiv does not return."""
    found = {p.id: p for p in await arxiv.by_ids(http, [p.id for p in papers], fetched)}
    return [merge([found[p.id], p])[0] for p in papers if p.id in found]
