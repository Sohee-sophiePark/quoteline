"""Async google-genai adapter for LLMClient (structured output only; google-genai 2.28.0)."""

import json
import time

from google import genai
from google.genai import errors, types

from quoteline.config import gemini_api_key
from quoteline.llm.base import FatalLLMError, LLMRequest, LLMResponse, RetryableLLMError

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


def to_config(req: LLMRequest) -> types.GenerateContentConfig:
    cfg = types.GenerateContentConfig(
        system_instruction=req.system,
        temperature=req.temperature,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if req.max_output_tokens:
        cfg.max_output_tokens = req.max_output_tokens
    if req.response_schema:
        cfg.response_mime_type, cfg.response_schema = "application/json", req.response_schema
    return cfg


def retry_after(e: errors.APIError) -> float | None:
    details = e.details.get("error", {}).get("details", []) if isinstance(e.details, dict) else []
    delays = [d["retryDelay"] for d in details if isinstance(d, dict) and "retryDelay" in d]
    return float(delays[0].rstrip("s")) if delays else None


class GeminiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.client = genai.Client(api_key=api_key or gemini_api_key())

    async def generate(self, req: LLMRequest) -> LLMResponse:
        t0 = time.monotonic()
        try:
            resp = await self.client.aio.models.generate_content(
                model=req.model, contents=req.user, config=to_config(req)
            )
        except errors.APIError as e:
            if e.code in RETRYABLE_CODES:
                raise RetryableLLMError(e.code, retry_after(e), e.message) from e
            raise FatalLLMError(f"{e.code} {e.message}") from e
        text = resp.text
        usage = resp.usage_metadata
        tokens_in = (usage.prompt_token_count or 0) if usage else 0
        return LLMResponse(
            text=text,
            parsed=json.loads(text) if req.response_schema and text else None,
            tokens_in=tokens_in,
            tokens_out=((usage.total_token_count or 0) - tokens_in) if usage else 0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            model=req.model,
        )

    async def list_models(self) -> list[str]:
        return [m.name or "" async for m in await self.client.aio.models.list()]
