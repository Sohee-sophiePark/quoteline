"""Typed settings loaded from config/settings.yaml; RUN_MODE env overrides run_mode."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
Agent = Literal["planner", "reader", "writer", "evaluator", "dataset"]


class RateLimitsCfg(BaseModel):
    max_concurrency: int
    per_model: dict[str, int]

    def rpm_for(self, model: str) -> int:
        return self.per_model.get(model, 5)


class RetryCfg(BaseModel):
    max_attempts: int
    base_seconds: float
    cap_seconds: float
    max_wait_seconds: float


class LoopCfg(BaseModel):
    max_revisions: int
    pass_min_score: int


class ResearchCfg(BaseModel):
    max_subquestions: int
    arms_per_subquestion: int
    top_k: int


class SourcesCfg(BaseModel):
    min_interval: dict[str, float]
    backoff_seconds: float
    timeout_seconds: float
    max_attempts: int
    user_agent: str


class BanditCfg(BaseModel):
    alpha: float
    seeds: int
    test_fraction: float
    bootstrap: int


class FeedCfg(BaseModel):
    categories: list[str]
    window_days: int
    half_life_days: float
    trending_size: int
    new_size: int


class Settings(BaseModel):
    run_mode: Literal["live", "record", "replay"]
    models: dict[Agent, str]
    fallback_models: list[str]
    temperature: dict[Agent, float]
    max_output_tokens: dict[Agent, int]
    rate_limits: RateLimitsCfg
    retry: RetryCfg
    per_call_timeout_seconds: float
    loop: LoopCfg
    research: ResearchCfg
    sources: SourcesCfg
    bandit: BanditCfg
    feed: FeedCfg
    paths: dict[str, str]

    def path(self, key: str) -> Path:
        return ROOT / self.paths[key]


def load_settings(path: Path = ROOT / "config" / "settings.yaml") -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    limits = raw.pop("rate_limits")
    raw["rate_limits"] = {
        "max_concurrency": limits.pop("max_concurrency"),
        "per_model": {m: v["rpm"] for m, v in limits.items()},
    }
    raw["run_mode"] = os.environ.get("RUN_MODE", raw["run_mode"])
    return Settings.model_validate(raw)


@lru_cache
def settings() -> Settings:
    return load_settings()


def gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set; export it in your shell (never read from .env)")
    return key
