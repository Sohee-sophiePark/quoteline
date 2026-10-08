"""Render {{p:id}} placeholders as numbered citations with references built from paper metadata."""

from pydantic import BaseModel

from quoteline.gates import CITE
from quoteline.models import Draft, Paper


class Reference(BaseModel):
    n: int
    id: str
    title: str
    authors: str
    year: str
    url: str
    contribution_quote: str = ""


class Rendered(BaseModel):
    takeaway: str
    paragraphs: list[str]
    references: list[Reference]


def authors_short(names: list[str]) -> str:
    return names[0] + (" et al." if len(names) > 1 else "") if names else "Unknown authors"


def render(draft: Draft, papers: dict[str, Paper]) -> Rendered:
    order: dict[str, int] = {}
    quotes = {c.paper_id: c.contribution_quote for c in draft.papers}

    def sub(text: str) -> str:
        def one(m) -> str:
            pid = m.group(1)
            if pid not in papers:
                return "[?]"
            return f"[{order.setdefault(pid, len(order) + 1)}]"

        return CITE.sub(one, text)

    takeaway, paragraphs = sub(draft.takeaway), [sub(p) for p in draft.paragraphs]
    refs = [
        Reference(
            n=n,
            id=pid,
            title=papers[pid].title,
            authors=authors_short(papers[pid].authors),
            year=papers[pid].published[:4],
            url=papers[pid].url,
            contribution_quote=quotes.get(pid, ""),
        )
        for pid, n in order.items()
    ]
    return Rendered(takeaway=takeaway, paragraphs=paragraphs, references=refs)


def markdown(question: str, r: Rendered) -> str:
    refs = "\n".join(
        f"{x.n}. {x.title} — {x.authors}, {x.year}. [arXiv:{x.id}]({x.url})" for x in r.references
    )
    body = "\n\n".join(r.paragraphs)
    return f"# {question}\n\n**{r.takeaway}**\n\n{body}\n\n## References\n\n{refs}\n"
