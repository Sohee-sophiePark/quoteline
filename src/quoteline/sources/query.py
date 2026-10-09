"""Query-style helpers: content-word extraction and arXiv ID normalisation."""

import re

STOPWORDS = set(
    "a an the of in on for to and or with without by from at as is are was were be been being "
    "what which who whom whose when where why how does do did can could should would will may "
    "might "
    "this that these those it its their there than then into about over under between across via "
    "recent latest new current most more best main key work works paper papers approach approaches "
    "method methods use used using make makes improve improves".split()
)


def terms(text: str, limit: int = 6) -> list[str]:
    """Up to `limit` distinct lowercase content words, in order of appearance."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", text.lower())
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS))[:limit]


def arxiv_id(raw: str) -> str | None:
    """Bare arXiv ID (new-style, no version) from an ID or abs/pdf URL, else None."""
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", raw)
    return m.group(1) if m else None


def arxiv_ids(text: str) -> list[str]:
    """Distinct new-style arXiv IDs mentioned in free text or arxiv.org links, in order."""
    return list(dict.fromkeys(re.findall(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d.])", text)))
