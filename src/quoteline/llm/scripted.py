"""Scripted LLMClient for offline tests: a function maps each request to a parsed response."""

import json
from collections.abc import Callable

from quoteline.llm.base import LLMRequest, LLMResponse


class ScriptedClient:
    def __init__(self, script: Callable[[LLMRequest], dict]) -> None:
        self.script = script
        self.calls: list[LLMRequest] = []

    async def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        parsed = self.script(req)
        return LLMResponse(
            text=json.dumps(parsed), parsed=parsed, model=req.model, source="scripted"
        )
