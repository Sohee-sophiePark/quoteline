"""OpenAlex works search (CC0), kept only when a location links an arXiv abstract page."""

import os
import re

from quoteline.models import Paper, Style
from quoteline.sources.http import PoliteHttp
from quoteline.sources.query import arxiv_id, terms

WORKS = "https://api.openalex.org/works"


def parse(results: list[dict], fetched: str) -> list[Paper]:
    papers = []
    for w in results:
        urls = [loc.get("landing_page_url") or "" for loc in w.get("locations", [])]
        pid = next((arxiv_id(u) for u in urls if "arxiv.org/abs/" in u), None)
        if pid and pid not in {p.id for p in papers}:
            title = " ".join((w.get("title") or "").split())
            papers.append(
                Paper(
                    id=pid,
                    title=title,
                    published=w.get("publication_date") or "",
                    sources=["openalex"],
                    fetched=fetched,
                )
            )
    return papers


def params(text: str, style: Style, fetched: str) -> dict:
    q = re.sub(r"[*?]", " ", text).strip() if style == "conceptual" else " ".join(terms(text))
    out = {"search": q, "per_page": 25, "select": "id,title,publication_date,locations"}
    if style == "recent":
        out["filter"] = f"from_publication_date:{int(fetched[:4]) - 1}-01-01"
    return out


async def search(http: PoliteHttp, text: str, style: Style, k: int, fetched: str) -> list[Paper]:
    key = os.environ.get("OPENALEX_API_KEY")
    headers = {"Authorization": f"Bearer {key}"} if key else None
    resp = await http.get(WORKS, params(text, style, fetched), headers=headers)
    return parse(resp.json().get("results", []), fetched)[:k]
