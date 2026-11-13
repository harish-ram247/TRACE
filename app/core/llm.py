"""LLM access behind one small interface.

- `OpenAICompatibleClient` talks to any provider exposing the OpenAI-style
  `POST {base_url}/chat/completions` endpoint (most hosted free tiers do). Choosing a provider is
  configuration: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.
- It spaces requests to stay under a requests-per-minute budget and retries rate-limit and
  server errors with backoff (honouring Retry-After).
- `CachedLLM` stores every response on disk keyed by model, messages and settings, so re-running
  an experiment costs no quota and returns identical text.
- `FakeLLM` is for tests; nothing in the test suite calls a real provider.

The API key is never logged or written to the cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


class LLMError(RuntimeError):
    pass


class LLMNotConfigured(LLMError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    cached: bool = False


class LLMClient(Protocol):
    name: str

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse: ...


class RateLimiter:
    """Spaces calls evenly: at most `per_minute` calls per 60 seconds."""

    def __init__(
        self,
        per_minute: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._clock, self._sleep = clock, sleep
        self._next = 0.0

    def wait(self) -> None:
        now = self._clock()
        if now < self._next:
            self._sleep(self._next - now)
            now = self._next
        self._next = now + self.interval


class OpenAICompatibleClient:
    RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        *,
        requests_per_minute: float = 10,
        max_retries: int = 5,
        timeout_s: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not (base_url and model and api_key):
            raise LLMNotConfigured("set LLM_BASE_URL, LLM_MODEL and LLM_API_KEY in .env")
        self.name = model
        self.model = model
        self.max_retries = max_retries
        self._sleep = sleep
        self._limiter = RateLimiter(requests_per_minute, sleep=sleep)
        verify: ssl.SSLContext | bool = True
        if transport is None:
            import truststore  # OS trust store: works behind TLS-inspecting antivirus/proxies

            verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
            transport=transport,
            verify=verify,
        )

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        for attempt in range(self.max_retries + 1):
            self._limiter.wait()
            started = time.perf_counter()
            try:
                resp = self._http.post("/chat/completions", json=body)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise LLMError(f"network error: {exc}") from exc
                self._backoff(attempt, None)
                continue
            if resp.status_code in self.RETRY_STATUS and attempt < self.max_retries:
                log.warning("LLM HTTP %s, retrying (attempt %s)", resp.status_code, attempt + 1)
                self._backoff(attempt, resp.headers.get("retry-after"))
                continue
            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            try:
                text = data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"unexpected response shape: {str(data)[:500]}") from exc
            usage = data.get("usage") or {}
            return LLMResponse(
                text=text,
                model=data.get("model") or self.model,
                tokens_in=usage.get("prompt_tokens"),
                tokens_out=usage.get("completion_tokens"),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        raise LLMError("retries exhausted")  # pragma: no cover

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay = min(2.0**attempt, 60.0)
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        self._sleep(delay)


class CachedLLM:
    """Disk cache in front of any client. Same request -> same stored response."""

    def __init__(self, inner: LLMClient, cache_dir: str | Path):
        self.inner = inner
        self.name = inner.name
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _key(self, messages, temperature, max_tokens, json_mode) -> str:
        payload = json.dumps(
            {
                "model": self.inner.name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_mode": json_mode,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        key = self._key(messages, temperature, max_tokens, json_mode)
        path = self.dir / key[:2] / f"{key}.json"
        if path.exists():
            stored = json.loads(path.read_text("utf-8"))
            return LLMResponse(**{**stored["response"], "cached": True})
        response = self.inner.complete(
            messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"request": {"messages": messages, "temperature": temperature,
                              "max_tokens": max_tokens, "json_mode": json_mode},
                  "response": asdict(response)}  # fmt: skip
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(path)
        return response


class FakeLLM:
    """Test double: answers with `responder(messages)` and records every call."""

    def __init__(self, responder: Callable[[list[Message]], str], name: str = "fake-llm"):
        self.name = name
        self._responder = responder
        self.calls: list[dict] = []

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "json_mode": json_mode})
        return LLMResponse(text=self._responder(messages), model=self.name)


@lru_cache
def get_llm() -> LLMClient:
    s = get_settings()
    client = OpenAICompatibleClient(
        s.llm_base_url,
        s.llm_model,
        s.llm_api_key.get_secret_value(),
        requests_per_minute=s.llm_requests_per_minute,
    )
    return CachedLLM(client, s.llm_cache_dir) if s.llm_cache_dir else client
