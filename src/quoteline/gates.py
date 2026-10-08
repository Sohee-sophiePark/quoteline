"""Deterministic gates G1–G5 over a writer draft; untrusted-content wrapping; injection flags."""

import re

from quoteline.models import Draft, GateResult, Paper

CITE = re.compile(r"\{\{p:([^}]+)\}\}")
YEAR = re.compile(r"\b(19|20)\d{2}\b")
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)"
    r"|disregard (the )?(system|previous)"
    r"|you are now|system prompt|new instructions:|</?untrusted>",
    re.IGNORECASE,
)


def norm(text: str) -> str:
    return " ".join(text.split()).lower()


def wrap(label: str, text: str, **attrs: str) -> str:
    """Untrusted content as data; tag look-alikes inside are neutralised."""
    body = re.sub(r"</?untrusted[^>]*>", "[tag removed]", text, flags=re.IGNORECASE)
    extra = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return f'<untrusted kind="{label}"{extra}>\n{body}\n</untrusted>'


def injection_flags(items: dict[str, str]) -> list[str]:
    return [
        f"{key}: {m.group(0)!r}" for key, text in items.items() if (m := INJECTION.search(text))
    ]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())
    return [s for s in parts if s.strip()]


def check(draft: Draft, papers: dict[str, Paper], question: str) -> list[GateResult]:
    body = [draft.takeaway, *draft.paragraphs]
    cited = {c for t in body for c in CITE.findall(t)} | {p.paper_id for p in draft.papers}
    unknown = sorted(cited - papers.keys())
    bad_quotes = [
        p.paper_id
        for p in draft.papers
        if p.paper_id in papers
        and norm(p.contribution_quote) not in norm(papers[p.paper_id].abstract)
    ]
    uncited = [s for t in body for s in sentences(t) if not CITE.search(s)]
    stripped = [CITE.sub("", t) for t in body]
    years = [m.group(0) for t in stripped for m in YEAR.finditer(t)]
    authors = [t for t in stripped if "et al" in t]
    flags = injection_flags(
        {"question": question, **{f"abstract {k}": p.abstract for k, p in papers.items()}}
    )
    return [
        GateResult(gate="G1 citations resolve", passed=not unknown, details=unknown),
        GateResult(gate="G2 quotes exact", passed=not bad_quotes, details=bad_quotes),
        GateResult(gate="G3 every sentence cited", passed=not uncited, details=uncited),
        GateResult(
            gate="G4 metadata from tools", passed=not (years or authors), details=years + authors
        ),
        GateResult(gate="G5 untrusted content", passed=True, details=flags),
    ]
