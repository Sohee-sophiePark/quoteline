"""Polite read-only HTTP GET: one connection and a minimum interval per host; retries 429/5xx."""

import asyncio
import re
import time
from urllib.parse import urlparse

import httpx

from quoteline.config import SourcesCfg

RETRY_STATUS = {429, 500, 502, 503, 504}


def server_wait(resp: httpx.Response) -> float | None:
    """Seconds the server asks us to wait: Retry-After, or `t=` in a RateLimit header."""
    if (ra := resp.headers.get("retry-after", "")).isdigit():
        return float(ra)
    m = re.search(r"\bt=(\d+)", resp.headers.get("ratelimit", ""))
    return float(m.group(1)) + 1 if m else None


class PoliteHttp:
    def __init__(self, cfg: SourcesCfg, sleep=asyncio.sleep, clock=time.monotonic) -> None:
        self.cfg, self.sleep, self.clock = cfg, sleep, clock
        self.client = httpx.AsyncClient(
            timeout=cfg.timeout_seconds,
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
        )
        self.locks: dict[str, asyncio.Lock] = {}
        self.last: dict[str, float] = {}
        self.requests = 0

    async def get(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        """GET `url`; raises httpx.HTTPStatusError once retries are exhausted."""
        host = urlparse(url).hostname or ""
        lock = self.locks.setdefault(host, asyncio.Lock())
        async with lock:
            for attempt in range(1, self.cfg.max_attempts + 1):
                gap = self.cfg.min_interval.get(host, 1.0) - (
                    self.clock() - self.last.get(host, float("-inf"))
                )
                if gap > 0:
                    await self.sleep(gap)
                resp = await self.client.get(url, params=params, headers=headers)
                self.last[host] = self.clock()
                self.requests += 1
                if resp.status_code not in RETRY_STATUS or attempt == self.cfg.max_attempts:
                    return resp.raise_for_status()
                await self.sleep(min(300.0, server_wait(resp) or 5.0 * 2 ** (attempt - 1)))
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self.client.aclose()
