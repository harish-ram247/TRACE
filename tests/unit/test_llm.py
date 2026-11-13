import json

import httpx
import pytest

from app.core.llm import (
    CachedLLM,
    FakeLLM,
    LLMError,
    LLMNotConfigured,
    OpenAICompatibleClient,
    RateLimiter,
)

OK_BODY = {
    "model": "m-2026-01",
    "choices": [{"message": {"role": "assistant", "content": "hello"}}],
    "usage": {"prompt_tokens": 7, "completion_tokens": 2},
}
MSGS = [{"role": "user", "content": "hi"}]


def client_with(handler, **kw):
    sleeps: list[float] = []
    client = OpenAICompatibleClient(
        "https://llm.example/v1",
        "m",
        "secret-key",
        requests_per_minute=0,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        **kw,
    )
    return client, sleeps


def test_request_shape_auth_and_parsed_response():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=OK_BODY)

    client, _ = client_with(handler)
    r = client.complete(MSGS, max_tokens=50, json_mode=True)
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["max_tokens"] == 50 and seen["body"]["temperature"] == 0.0
    assert (r.text, r.model, r.tokens_in, r.tokens_out) == ("hello", "m-2026-01", 7, 2)


def test_json_mode_off_sends_no_response_format():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    client_with(handler)[0].complete(MSGS)
    assert "response_format" not in bodies[0]


def test_rate_limit_is_retried_with_retry_after():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"retry-after": "7"}, text="slow down")
        return httpx.Response(200, json=OK_BODY)

    client, sleeps = client_with(handler)
    assert client.complete(MSGS).text == "hello"
    assert calls["n"] == 3
    assert sleeps == [7.0, 7.0]


def test_client_errors_are_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="bad key")

    client, _ = client_with(handler)
    with pytest.raises(LLMError, match="401"):
        client.complete(MSGS)
    assert calls["n"] == 1


def test_retries_give_up_eventually():
    client, sleeps = client_with(lambda r: httpx.Response(503), max_retries=2)
    with pytest.raises(LLMError, match="503"):
        client.complete(MSGS)
    assert len(sleeps) == 2


def test_missing_configuration_is_a_clear_error():
    with pytest.raises(LLMNotConfigured):
        OpenAICompatibleClient("", "m", "k")


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    slept = []

    def sleep(s):
        slept.append(s)
        t["now"] += s

    limiter = RateLimiter(30, clock=lambda: t["now"], sleep=sleep)  # one call per 2 s
    for _ in range(3):
        limiter.wait()
    assert slept == [2.0, 2.0]


def test_cache_returns_stored_response_without_calling_again(tmp_path):
    fake = FakeLLM(lambda m: "answer")
    cached = CachedLLM(fake, tmp_path)
    first = cached.complete(MSGS)
    second = cached.complete(MSGS)
    assert (first.cached, second.cached) == (False, True)
    assert second.text == "answer" and len(fake.calls) == 1


def test_cache_key_depends_on_settings(tmp_path):
    fake = FakeLLM(lambda m: "x")
    cached = CachedLLM(fake, tmp_path)
    cached.complete(MSGS)
    cached.complete(MSGS, json_mode=True)
    cached.complete(MSGS, max_tokens=99)
    assert len(fake.calls) == 3


def test_cache_never_stores_the_api_key(tmp_path):
    client, _ = client_with(lambda r: httpx.Response(200, json=OK_BODY))
    CachedLLM(client, tmp_path).complete(MSGS)
    stored = "".join(p.read_text("utf-8") for p in tmp_path.rglob("*.json"))
    assert "secret-key" not in stored and "hello" in stored
