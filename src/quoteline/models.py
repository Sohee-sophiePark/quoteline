"""Domain models: papers, arms, agent outputs, gate results and evaluator verdicts."""

from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["arxiv", "hf", "openalex"]
Style = Literal["keyword", "conceptual", "recent"]
SOURCES: tuple[Source, ...] = ("arxiv", "hf", "openalex")
STYLES: tuple[Style, ...] = ("keyword", "conceptual", "recent")


class Paper(BaseModel):
    id: str  # arXiv ID without version
    title: str
    authors: list[str] = []
    published: str = ""  # YYYY-MM-DD
    abstract: str = ""
    categories: list[str] = []
    upvotes: int | None = None
    sources: list[str] = []
    fetched: str = ""  # YYYY-MM-DD

    @property
    def url(self) -> str:
        return f"https://arxiv.org/abs/{self.id}"


class Arm(BaseModel):
    source: Source
    style: Style

    @property
    def name(self) -> str:
        return f"{self.source}:{self.style}"


ARMS: list[Arm] = [Arm(source=s, style=t) for s in SOURCES for t in STYLES]


class SubQuestion(BaseModel):
    text: str = Field(description="A focused sub-question answerable from paper abstracts")


class Plan(BaseModel):
    subquestions: list[SubQuestion]


class Claim(BaseModel):
    paper_id: str
    quote: str = Field(description="Exact span copied from the paper's abstract")
    claim: str = Field(description="What the quote supports, one sentence")


class Reading(BaseModel):
    claims: list[Claim]


class CitedPaper(BaseModel):
    paper_id: str
    contribution_quote: str = Field(description="Exact abstract span stating what the paper claims")


class Draft(BaseModel):
    takeaway: str = Field(description="One sentence practical takeaway, with {{p:<id>}} citations")
    paragraphs: list[str] = Field(description="Every sentence cites with {{p:<id>}}")
    papers: list[CitedPaper]


class Verdict(BaseModel):
    faithfulness: int = Field(ge=1, le=5)
    coverage: int = Field(ge=1, le=5)
    issues: list[str] = []


class GateResult(BaseModel):
    gate: str
    passed: bool
    details: list[str] = []


class KnownItemQuestion(BaseModel):
    paper_id: str
    question: str


class KnownItemBatch(BaseModel):
    questions: list[KnownItemQuestion]


class Judgment(BaseModel):
    paper_id: str
    relevant: bool


class JudgmentBatch(BaseModel):
    judgments: list[Judgment]
