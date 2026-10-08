import datetime as dt
from pathlib import Path

import httpx
import numpy as np
import pytest

from quoteline.config import settings
from quoteline.dataset import (
    generate_questions,
    golden_matrix,
    known_item_matrix,
    leaks_title,
    sample_dates,
    style_for,
)
from quoteline.feed import build, rank_new, rank_trending
from quoteline.harness import Runner, Trace
from quoteline.llm.scripted import ScriptedClient
from quoteline.models import ARMS, Paper
from quoteline.sources.http import PoliteHttp

TODAY = "2026-10-08"


def p(pid, published, upvotes=None, sources=("hf",)):
    return Paper(id=pid, title=pid, published=published, upvotes=upvotes, sources=list(sources))


def test_trending_decays_with_age_and_ignores_unvoted():
    papers = [p("old", "2026-10-02", 100), p("new", "2026-10-08", 30), p("none", "2026-10-08")]
    ranked = rank_trending(papers, TODAY, half_life=3.0, n=5)
    assert [x.id for x, _ in ranked] == ["new", "old"]
    assert ranked[1][1] == np.float64(1.0 * 0.5**2)


def test_new_section_newest_first_arxiv_only_excluding_trending():
    papers = [
        p("a", "2026-10-07", sources=["arxiv"]),
        p("b", "2026-10-08", sources=["arxiv"]),
        p("c", "2026-10-08", sources=["hf"]),
        p("d", "2026-10-08", sources=["arxiv", "hf"]),
    ]
    assert [x.id for x in rank_new(papers, 5, exclude={"d"})] == ["b", "a"]


def test_sample_dates_are_weekdays_and_spread():
    dates = sample_dates(dt.date(2023, 6, 1), dt.date(2026, 9, 30), 46)
    assert len(dates) == 46 and dates[0] == "2023-06-01"
    assert all(dt.date.fromisoformat(d).weekday() < 5 for d in dates)


def test_style_recent_only_for_young_papers():
    assert style_for(p("x", "2026-09-01"), 0, TODAY) == "recent"
    assert style_for(p("x", "2023-09-01"), 0, TODAY) == "fact"


def test_leaks_title():
    title = "SpecDec: Speculative Decoding for Seq2seq Generation"
    assert leaks_title("What does SpecDec do?", title)
    assert leaks_title("speculative decoding for seq2seq generation?", title)
    assert not leaks_title("How can a draft model speed up autoregressive text output?", title)


async def test_generate_questions_filters_leaks_and_unknown_ids():
    targets = [Paper(id="1", title="Alpha Beta Gamma", abstract="x", published="2024-01-01")]

    def respond(req):
        assert 'style="fact"' in req.user
        return {
            "questions": [
                {"paper_id": "1", "question": "How is the thing done better?"},
                {"paper_id": "1", "question": "What is alpha beta gamma?"},
                {"paper_id": "9", "question": "Unknown paper?"},
            ]
        }

    rows = await generate_questions(
        Runner(settings(), ScriptedClient(respond), Trace()), targets, TODAY
    )
    assert rows == [{"question": "How is the thing done better?", "target": "1"}]


def test_reward_matrices():
    arms = {a.name: [] for a in ARMS}
    row = {"qid": "q", "question": "How?", "target": "t", "arms": {**arms, "hf:recent": ["t", "u"]}}
    X, R = known_item_matrix([row])
    assert (
        X.shape == (1, 7) and R.sum() == 1 and R[0, [a.name for a in ARMS].index("hf:recent")] == 1
    )
    _, G = golden_matrix([row], {"q": {"t": True, "u": False}}, k=5)
    assert G.max() == 0.2


@pytest.mark.parametrize("failure", ["refused", "timeout"])
async def test_feed_survives_arxiv_api_failure(failure):
    fx = Path(__file__).parent / "fixtures"

    def handler(req):
        if req.url.host == "rss.arxiv.org":
            return httpx.Response(200, text=(fx / "rss.xml").read_text())
        if req.url.host == "huggingface.co":
            return httpx.Response(200, text=(fx / "hf_daily.json").read_text())
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(429)

    async def no_sleep(s):
        pass

    http = PoliteHttp(settings().sources, sleep=no_sleep)
    http.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    feed = await build(http, settings().feed, "2026-10-08")
    assert feed["trending"] and all(p["abstract"] for p in feed["trending"])
    assert "2610.06889" in [p["id"] for p in feed["new"]]
