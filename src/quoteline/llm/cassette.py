"""Record/replay wrapper keyed by a hash of the request, for deterministic tests and CI."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from quoteline.llm.base import LLMClient, LLMRequest, LLMResponse


class CassetteMiss(KeyError):
    def __init__(self, key: str, purpose: str) -> None:
        super().__init__(f"no cassette entry for {purpose} ({key[:12]}); record it first")
        self.key, self.purpose = key, purpose


def request_key(req: LLMRequest) -> str:
    payload = req.model_dump(exclude={"response_schema", "purpose"})
    payload["schema_name"] = req.response_schema.__name__ if req.response_schema else None
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class CassetteClient:
    """Serves stored requests in order; `record` calls `inner` only for new requests."""

    def __init__(
        self, path: Path, mode: Literal["record", "replay"], inner: LLMClient | None = None
    ) -> None:
        self.path, self.mode, self.inner = path, mode, inner
        self.entries: dict[str, list[dict]] = {}
        self.served: dict[str, int] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                self.entries.setdefault(entry["key"], []).append(entry)

    async def generate(self, req: LLMRequest) -> LLMResponse:
        key = request_key(req)
        if key in self.entries or self.mode == "replay":
            if key not in self.entries:
                raise CassetteMiss(key, req.purpose)
            n = self.served.get(key, 0)
            self.served[key] = n + 1
            entry = self.entries[key][min(n, len(self.entries[key]) - 1)]
            return LLMResponse.model_validate(entry["response"]).model_copy(
                update={"source": "cassette"}
            )
        assert self.inner is not None, "record mode needs an inner client"
        resp = await self.inner.generate(req)
        entry = {"key": key, "purpose": req.purpose, "response": resp.model_dump()}
        self.entries.setdefault(key, []).append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return resp
