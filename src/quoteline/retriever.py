"""Runs (arm, query) pairs in parallel, merges, fills arXiv text; record/replay via JSONL."""

import asyncio
import json
from pathlib import Path
from typing import Literal

from quoteline.models import Arm, Paper
from quoteline.sources import arxiv
from quoteline.sources.http import PoliteHttp
from quoteline.sources.retrieve import canonical, merge, run_arm

Pair = tuple[Arm, str]


def key(arm: Arm, text: str) -> str:
    return f"{arm.name}|{text}"


class Retriever:
    """`live` fetches; `record` serves stored results and fetches the rest; `replay` serves only."""

    def __init__(
        self,
        mode: Literal["live", "record", "replay"],
        path: Path,
        http: PoliteHttp | None = None,
        k: int = 5,
        today: str = "",
    ) -> None:
        self.mode, self.path, self.http, self.k, self.today = mode, path, http, k, today
        self.store: dict[str, list[Paper]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                e = json.loads(line)
                self.store[e["key"]] = [Paper.model_validate(p) for p in e["papers"]]

    async def lookup(self, ids: list[str]) -> list[Paper]:
        """Papers by arXiv ID (canonical arXiv metadata), recorded and replayed like searches."""
        k = "lookup|" + ",".join(ids)
        if k in self.store or self.mode == "replay":
            return self.store[k]
        assert self.http is not None
        papers = await arxiv.by_ids(self.http, ids, self.today)
        if self.mode == "record":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": k, "papers": [p.model_dump() for p in papers]}) + "\n")
            self.store[k] = papers
        return papers

    async def retrieve(self, pairs: list[Pair]) -> dict[str, list[Paper]]:
        cached = {key(a, t): self.store[key(a, t)] for a, t in pairs if key(a, t) in self.store}
        pairs = [(a, t) for a, t in pairs if key(a, t) not in cached]
        if self.mode == "replay" or not pairs:
            if pairs:
                raise KeyError(f"no recorded retrieval for {key(*pairs[0])}")
            return cached
        assert self.http is not None
        raw = await asyncio.gather(
            *(run_arm(self.http, a, t, self.k, self.today) for a, t in pairs)
        )
        filled = {
            p.id: p
            for p in await canonical(self.http, merge([p for r in raw for p in r]), self.today)
        }
        out = {
            key(a, t): [filled[p.id] for p in r if p.id in filled]
            for (a, t), r in zip(pairs, raw, strict=True)
        }
        if self.mode == "record":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                for k_, papers in out.items():
                    f.write(
                        json.dumps({"key": k_, "papers": [p.model_dump() for p in papers]}) + "\n"
                    )
            self.store.update(out)
        return {**cached, **out}
