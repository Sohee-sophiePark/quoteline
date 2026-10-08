"""Per-run plumbing: trace events, LLM calls (limiter + live model fallback), client factory."""

import time
from pathlib import Path

from pydantic import BaseModel

from quoteline.config import Agent, Settings
from quoteline.llm.base import LLMClient, LLMRequest, RetryableLLMError
from quoteline.llm.cassette import CassetteClient
from quoteline.llm.limiter import RateLimiter


class Event(BaseModel):
    seq: int
    t_ms: int
    kind: str
    agent: str
    payload: dict = {}
    level: str = "info"


class Trace:
    def __init__(self, events: list[Event] | None = None) -> None:
        self.events = events or []
        self.t0 = time.monotonic()

    def emit(
        self, kind: str, agent: str, payload: dict | None = None, level: str = "info"
    ) -> Event:
        e = Event(
            seq=len(self.events),
            t_ms=int((time.monotonic() - self.t0) * 1000),
            kind=kind,
            agent=agent,
            payload=payload or {},
            level=level,
        )
        self.events.append(e)
        return e


def make_client(settings: Settings, cassette: Path) -> LLMClient:
    if settings.run_mode == "replay":
        return CassetteClient(cassette, "replay")
    from quoteline.llm.gemini import GeminiClient

    if settings.run_mode == "record":
        return CassetteClient(cassette, "record", GeminiClient())
    return GeminiClient()


class Runner:
    """`call` = limiter → client → trace; in live mode, 429/503 after retries switches model."""

    def __init__(self, settings: Settings, llm: LLMClient, trace: Trace) -> None:
        self.settings, self.llm, self.trace = settings, llm, trace
        self.limiter = RateLimiter(
            settings.rate_limits, settings.retry, settings.per_call_timeout_seconds
        )
        self.exhausted: set[str] = set()
        self.calls = 0

    async def call(
        self, agent: Agent, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        s = self.settings
        req = LLMRequest(
            model=s.models[agent],
            system=system,
            user=user,
            temperature=s.temperature[agent],
            max_output_tokens=s.max_output_tokens[agent],
            response_schema=schema,
            purpose=agent,
        )
        chain = [req.model, *s.fallback_models] if s.run_mode == "live" else [req.model]
        models = [m for m in dict.fromkeys(chain) if m not in self.exhausted] or [req.model]
        for i, model in enumerate(models):
            try:
                resp = await self.limiter.call(
                    model, lambda n, m=model: self.llm.generate(req.model_copy(update={"model": m}))
                )
                break
            except RetryableLLMError as e:
                if i == len(models) - 1 or e.status not in (429, 503):
                    raise
                self.exhausted.add(model)
                self.trace.emit(
                    "model_fallback", agent, {"from": model, "to": models[i + 1]}, "warn"
                )
        self.calls += 1
        self.trace.emit(
            "llm_call",
            agent,
            {
                "model": resp.model,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "latency_ms": resp.latency_ms,
                "source": resp.source,
            },
        )
        return schema.model_validate(resp.parsed)


def prompt(settings: Settings, name: str, **fmt: object) -> str:
    return (settings.path("prompts") / f"{name}.md").read_text(encoding="utf-8").format(**fmt)
