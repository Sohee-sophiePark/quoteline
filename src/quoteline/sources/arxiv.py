"""arXiv: API search and ID lookup (Atom), category RSS for the daily feed. Metadata is CC0."""

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from quoteline.models import Paper, Style
from quoteline.sources.http import PoliteHttp
from quoteline.sources.query import arxiv_id, terms

API = "https://export.arxiv.org/api/query"
RSS = "https://rss.arxiv.org/rss/{}"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_atom(xml: str, fetched: str) -> list[Paper]:
    papers = []
    for e in ET.fromstring(xml).findall("a:entry", NS):
        pid = arxiv_id(e.findtext("a:id", "", NS))
        if not pid:
            continue
        papers.append(
            Paper(
                id=pid,
                title=_clean(e.findtext("a:title", "", NS)),
                authors=[_clean(a.findtext("a:name", "", NS)) for a in e.findall("a:author", NS)],
                published=e.findtext("a:published", "", NS)[:10],
                abstract=_clean(e.findtext("a:summary", "", NS)),
                categories=[c.get("term", "") for c in e.findall("a:category", NS)],
                sources=["arxiv"],
                fetched=fetched,
            )
        )
    return papers


def parse_rss(xml: str, fetched: str) -> list[Paper]:
    """New announcements only (Announce Type: new); replacements and cross-lists are skipped."""
    channel = ET.fromstring(xml).find("channel")
    papers = []
    for item in channel.findall("item") if channel is not None else []:
        desc = item.findtext("description", "")
        pid = arxiv_id(item.findtext("link", ""))
        if not pid or "Announce Type: new" not in desc:
            continue
        pub = item.findtext("pubDate") or channel.findtext("pubDate") or ""
        papers.append(
            Paper(
                id=pid,
                title=_clean(item.findtext("title")),
                authors=[_clean(a) for a in item.findtext("dc:creator", "", NS).split(",") if a],
                published=parsedate_to_datetime(pub).date().isoformat() if pub else fetched,
                abstract=_clean(desc.split("Abstract:", 1)[-1]),
                categories=[c.text or "" for c in item.findall("category")],
                sources=["arxiv"],
                fetched=fetched,
            )
        )
    return papers


def search_query(text: str, style: Style) -> dict:
    words = terms(text)
    joiner = " OR " if style == "conceptual" else " AND "
    return {
        "search_query": joiner.join(f"all:{w}" for w in words),
        "sortBy": "submittedDate" if style == "recent" else "relevance",
        "sortOrder": "descending",
    }


async def search(http: PoliteHttp, text: str, style: Style, k: int, fetched: str) -> list[Paper]:
    resp = await http.get(API, {**search_query(text, style), "start": 0, "max_results": k})
    return parse_atom(resp.text, fetched)[:k]


async def by_ids(http: PoliteHttp, ids: list[str], fetched: str) -> list[Paper]:
    papers: list[Paper] = []
    for i in range(0, len(ids), 50):
        chunk = ids[i : i + 50]
        resp = await http.get(API, {"id_list": ",".join(chunk), "max_results": len(chunk)})
        papers += parse_atom(resp.text, fetched)
    return papers


async def rss(http: PoliteHttp, category: str, fetched: str) -> list[Paper]:
    return parse_rss((await http.get(RSS.format(category))).text, fetched)
