"""Hugging Face papers JSON API: daily papers (with upvotes) and paper search."""

from quoteline.models import Paper, Style
from quoteline.sources.http import PoliteHttp
from quoteline.sources.query import arxiv_id, terms

DAILY = "https://huggingface.co/api/daily_papers"
SEARCH = "https://huggingface.co/api/papers/search"


def parse(items: list[dict], fetched: str) -> list[Paper]:
    papers = []
    for item in items:
        p = item.get("paper", item)
        pid = arxiv_id(p.get("id", ""))
        if not pid:
            continue
        papers.append(
            Paper(
                id=pid,
                title=" ".join((p.get("title") or "").split()),
                authors=[a["name"] for a in p.get("authors", []) if a.get("name")],
                published=(p.get("publishedAt") or "")[:10],
                abstract=" ".join((p.get("summary") or "").split()),
                upvotes=p.get("upvotes", 0),
                sources=["hf"],
                fetched=fetched,
            )
        )
    return papers


async def daily(http: PoliteHttp, date: str, fetched: str) -> list[Paper]:
    return parse((await http.get(DAILY, {"date": date})).json(), fetched)


async def search(http: PoliteHttp, text: str, style: Style, k: int, fetched: str) -> list[Paper]:
    q = text if style == "conceptual" else " ".join(terms(text))
    papers = parse((await http.get(SEARCH, {"q": q})).json(), fetched)
    if style == "recent":
        papers = sorted(papers[: 4 * k], key=lambda p: p.published, reverse=True)
    return papers[:k]
