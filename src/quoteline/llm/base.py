"""LLMClient protocol, request/response models and the errors adapters raise."""

from typing import Literal, Protocol

from pydantic import BaseModel


class LLMRequest(BaseModel):
    model: str
    system: str
    user: str
    temperature: float = 0.0
    max_output_tokens: int | None = None
    response_schema: type[BaseModel] | None = None
    purpose: str


class LLMResponse(BaseModel):
    text: str | None = None
    parsed: dict | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    model: str = ""
    attempt: int = 1
    source: Literal["live", "cassette", "scripted"] = "live"


class LLMClient(Protocol):
    async def generate(self, req: LLMRequest) -> LLMResponse: ...


class RetryableLLMError(Exception):
    def __init__(self, status: int, retry_after_s: float | None = None, detail: str = "") -> None:
        super().__init__(f"{status} {detail}".strip())
        self.status, self.retry_after_s = status, retry_after_s


class FatalLLMError(Exception):
    pass
