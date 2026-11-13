"""Check the configured LLM provider with two tiny requests (plain text and JSON mode).

Usage: python -m app.core.llm_check

Bypasses the response cache so it really reaches the provider. Never prints the API key.
"""

from __future__ import annotations

import json
import sys

from app.core.config import get_settings
from app.core.llm import LLMError, OpenAICompatibleClient


def main() -> int:
    s = get_settings()
    try:
        client = OpenAICompatibleClient(
            s.llm_base_url,
            s.llm_model,
            s.llm_api_key.get_secret_value(),
            requests_per_minute=s.llm_requests_per_minute,
            max_retries=2,
        )
        plain = client.complete(
            [{"role": "user", "content": "Reply with exactly the word: pong"}], max_tokens=10
        )
        print(f"plain text  ok  model={plain.model}  {plain.latency_ms} ms  reply={plain.text!r}")
        structured = client.complete(
            [
                {"role": "system", "content": "Reply with a JSON object only."},
                {"role": "user", "content": 'Return {"status": "ok", "n": 3}'},
            ],
            max_tokens=30,
            json_mode=True,
        )
        parsed = json.loads(structured.text)
        print(f"json mode   ok  parsed={parsed}")
    except json.JSONDecodeError:
        print("json mode   FAILED: reply was not valid JSON; pick a model with JSON support")
        return 1
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
