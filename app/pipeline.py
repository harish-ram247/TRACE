"""Question in, cited answer out.

variant "temporal": parse the time reference (or use the caller's as_of), retrieve only chunk
                    versions valid then, answer with the dated prompt.
variant "plain":    the baseline: no time parsing, retrieval over every version ever stored,
                    answer with the undated prompt.
Claim verification (plan M7) is added on top of this later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import psycopg

from app.core.llm import LLMClient
from app.generation.answer import Answer, generate_answer
from app.retrieval.embeddings import Embedder
from app.retrieval.search import Hit, search
from app.temporal.parser import TimeParse, explicit, parse_time

Variant = Literal["temporal", "plain"]


@dataclass
class AskResult:
    question: str
    variant: Variant
    time: TimeParse | None
    hits: list[Hit]
    answer: Answer
    timings_ms: dict[str, int] = field(default_factory=dict)


def ask(
    conn: psycopg.Connection,
    question: str,
    *,
    embedder: Embedder,
    llm: LLMClient,
    repo_id: str,
    variant: Variant = "temporal",
    as_of: datetime | None = None,
    now: datetime | None = None,
    top_k: int = 5,
    llm_time_fallback: bool = False,
) -> AskResult:
    now = now or datetime.now(UTC)
    timings: dict[str, int] = {}

    def lap(name: str, started: float) -> None:
        timings[name] = int((time.perf_counter() - started) * 1000)

    t0 = time.perf_counter()
    if variant == "temporal":
        parsed = (
            explicit(as_of, now)
            if as_of is not None
            else parse_time(question, now, llm=llm if llm_time_fallback else None)
        )
    else:
        parsed = None
    lap("time_parse", t0)

    t0 = time.perf_counter()
    hits = search(
        conn,
        question,
        parsed.as_of if parsed else None,
        embedder=embedder,
        repo_id=repo_id,
        top_k=top_k,
        time_filter=variant == "temporal",
    )
    lap("retrieval", t0)

    t0 = time.perf_counter()
    answer = generate_answer(
        llm,
        question,
        hits,
        as_of=parsed.as_of if parsed else None,
        temporal=variant == "temporal",
        time_phrase=parsed.matched if parsed else None,
    )
    lap("generation", t0)
    return AskResult(question, variant, parsed, hits, answer, timings)
