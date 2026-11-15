"""Split an answer into atomic, self-contained claims with the sources each one cites.

The LLM returns JSON: {"claims": [{"text": "...", "sources": ["S1"]}]}. The output is validated;
on malformed output it retries once, and if that also fails it falls back to splitting the
answer into sentences and reading each sentence's [S#] citations (no LLM). The method used is
recorded so the evaluation can report how often the fallback was needed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.core.llm import LLMClient, LLMError

EXTRACT_VERSION = "claims-v1"
_LABEL = re.compile(r"S\d+")
_CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")

SYSTEM = """\
You split an answer into atomic factual claims for fact-checking.
Return a JSON object only: {"claims": [{"text": "...", "sources": ["S1"]}]}
Rules:
- One fact per claim. A claim must make sense on its own: replace pronouns with what they refer to.
- Keep option names, values and version numbers exactly as written in the answer, with backticks.
- "sources" lists the [S#] labels the answer cites for that fact; use [] if it cites none.
- Do not add facts that are not in the answer. Skip phrases that state no fact."""


@dataclass(frozen=True)
class Claim:
    text: str
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Extraction:
    claims: list[Claim]
    method: str  # "llm" | "llm_retry" | "sentence_fallback"


def _validate(raw: str) -> list[Claim]:
    data = json.loads(raw)
    items = data["claims"] if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("claims is not a list")
    claims = []
    for item in items:
        text = str(item["text"]).strip()
        sources = [s for s in item.get("sources", []) if isinstance(s, str) and _LABEL.fullmatch(s)]
        if text:
            claims.append(Claim(text, sources))
    return claims


def sentence_fallback(answer: str) -> list[Claim]:
    sentences = re.split(r"(?<=[.!?\]])\s+(?=[A-Z`])", answer.strip())
    claims = []
    for sentence in sentences:
        labels = [x.strip() for group in _CITE.findall(sentence) for x in group.split(",")]
        text = " ".join(_CITE.sub("", sentence).split())
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)  # "`5000` ." -> "`5000`."
        if text:
            claims.append(Claim(text, labels))
    return claims


def extract_claims(llm: LLMClient, answer: str) -> Extraction:
    if not answer.strip() or answer.strip().upper().startswith("NOT_FOUND"):
        return Extraction([], "none")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Answer:\n{answer}"},
    ]
    for attempt, method in enumerate(("llm", "llm_retry")):
        try:
            reply = llm.complete(messages, json_mode=True, max_tokens=500)
            return Extraction(_validate(reply.text), method)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": "(invalid output)"},
                    {"role": "user", "content": "That was not valid JSON in the required shape. "
                                                "Return only the JSON object."},
                ]  # fmt: skip
        except LLMError:
            break
    return Extraction(sentence_fallback(answer), "sentence_fallback")
