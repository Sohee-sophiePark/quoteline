import json
from pathlib import Path

import httpx
import pytest

from quoteline.config import settings
from quoteline.models import Paper
from quoteline.sources import arxiv, hf, openalex
from quoteline.sources.http import PoliteHttp
from quoteline.sources.query import arxiv_id, terms
from quoteline.sources.retrieve import merge

FX = Path(__file__).parent / "fixtures"
TODAY = "2026-10-07"


def test_terms_drop_stopwords_and_dedupe():
    assert terms("What are the latest methods for speculative decoding of LLMs, decoding?") == [
        "speculative",
        "decoding",
        "llms",
    ]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://arxiv.org/abs/2203.16487v6", "2203.16487"),
        ("https://arxiv.org/abs/2610.06889", "2610.06889"),
        ("2211.17192", "2211.17192"),
        ("https://doi.org/10.1000/xyz", None),
    ],
)
def test_arxiv_id(raw, expected):
    assert arxiv_id(raw) == expected


def test_parse_atom():
    papers = arxiv.parse_atom((FX / "arxiv_search.xml").read_text(), TODAY)
    assert [p.id for p in papers] == ["2203.16487", papers[1].id]
    p = papers[0]
    assert p.title.startswith("Speculative Decoding: Exploiting")
    assert p.abstract.startswith("We propose Speculative Decoding") and "\n" not in p.abstract
    assert p.authors and p.published[:4] == "2022" and p.sources == ["arxiv"]


def test_parse_rss_keeps_new_only():
    papers = arxiv.parse_rss((FX / "rss.xml").read_text(), TODAY)
    assert len(papers) == 2
    assert papers[0].id == "2610.06889"
    assert papers[0].abstract.startswith("We study the application")
    assert papers[0].published == "2026-10-07" and papers[0].authors


def test_parse_hf():
    papers = hf.parse(json.loads((FX / "hf_daily.json").read_text()), TODAY)
    assert len(papers) == 2 and papers[0].upvotes is not None and papers[0].abstract
    assert papers[0].authors and papers[0].sources == ["hf"]


def test_parse_openalex_keeps_arxiv_linked_only():
    papers = openalex.parse(json.loads((FX / "openalex.json").read_text())["results"], TODAY)
    assert [p.id for p in papers] == ["2402.01528", "2603.03251", "2310.07177"]
    assert all(p.abstract == "" for p in papers)


def test_arxiv_query_styles_differ():
    kw = arxiv.search_query("speculative decoding for LLMs", "keyword")
    assert kw["search_query"] == "all:speculative AND all:decoding AND all:llms"
    assert arxiv.search_query("alpha beta", "conceptual")["search_query"] == "all:alpha OR all:beta"
    assert arxiv.search_query("x y", "recent")["sortBy"] == "submittedDate"


def test_openalex_strips_wildcards():
    assert openalex.params("Why is it fast?", "conceptual", TODAY)["search"] == "Why is it fast"


def test_openalex_recent_filters_last_two_years():
    assert openalex.params("a b", "recent", TODAY)["filter"] == "from_publication_date:2025-01-01"


def test_merge_prefers_arxiv_text_keeps_upvotes():
    hf_p = Paper(id="1", title="HF", abstract="hf text", upvotes=7, sources=["hf"])
    ax_p = Paper(id="1", title="AX", abstract="arxiv text", authors=["A"], sources=["arxiv"])
    other = Paper(id="2", title="Other", sources=["openalex"])
    merged = merge([hf_p, other, ax_p])
    assert [p.id for p in merged] == ["1", "2"]
    assert merged[0].title == "AX" and merged[0].abstract == "arxiv text"
    assert merged[0].upvotes == 7 and merged[0].sources == ["hf", "arxiv"]


async def test_polite_http_spaces_requests_and_retries():
    calls, sleeps, now = [], [], [0.0]

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(429 if len(calls) == 1 else 200, text="ok")

    async def sleep(s):
        sleeps.append(s)
        now[0] += s

    http = PoliteHttp(settings().sources, sleep=sleep, clock=lambda: now[0])
    http.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    resp = await http.get("https://export.arxiv.org/api/query")
    assert resp.text == "ok" and len(calls) == 2
    assert sleeps == [5.0]
    await http.get("https://export.arxiv.org/api/query")
    assert sleeps[-1] == pytest.approx(3.1)


def test_server_wait_reads_retry_after_and_ratelimit():
    from quoteline.sources.http import server_wait

    assert server_wait(httpx.Response(429, headers={"retry-after": "12"})) == 12.0
    assert server_wait(httpx.Response(429, headers={"ratelimit": '"search";r=0;t=76'})) == 77.0
    assert server_wait(httpx.Response(429)) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Luka Radi\\'c", "Luka Radić"),
        ("Ana Rodr\\'iguez", "Ana Rodríguez"),
        ('J{\\"o}rg', "Jörg"),
        ("Du\\v{s}an", "Dušan"),
        ("Mar{\\'\\i}a", "María"),
        ("Plain Name", "Plain Name"),
    ],
)
def test_untex_author_names(raw, expected):
    assert arxiv.untex(raw) == expected
