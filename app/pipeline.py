"""Question in, cited answer out.

Variants (project_plan.md section 10.1):
  plain              V0  no time parsing, retrieval over every version, undated prompt
  temporal           V1  parse the time (or use the caller's as_of), retrieve only versions valid
                         then, dated prompt
  plain_verified     V2  plain + claim verification (entailment only: no date to check against)
  temporal_verified  V3  temporal + claim verification with the validity check
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
from app.verification.nli import NLIModel
from app.verification.verify import DEFAULT_THRESHOLD, Verification, verified_answer

Variant = Literal["plain", "temporal", "plain_verified", "temporal_verified"]
VARIANTS: tuple[Variant, ...] = ("plain", "temporal", "plain_verified", "temporal_verified")


@dataclass
class AskResult:
    question: str
    variant: Variant
    time: TimeParse | None
    hits: list[Hit]
    answer: Answer
    timings_ms: dict[str, int] = field(default_factory=dict)
    verification: Verification | None = None


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
    nli: NLIModel | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> AskResult:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    temporal = variant.startswith("temporal")
    verify = variant.endswith("_verified")
    if verify and nli is None:
        raise ValueError(f"variant {variant!r} needs an NLI model")
    now = now or datetime.now(UTC)
    timings: dict[str, int] = {}

    def lap(name: str, started: float) -> None:
        timings[name] = int((time.perf_counter() - started) * 1000)

    t0 = time.perf_counter()
    if temporal:
        parsed = (
            explicit(as_of, now)
            if as_of is not None
            else parse_time(question, now, llm=llm if llm_time_fallback else None)
        )
    else:
        parsed = None
    lap("time_parse", t0)
    as_of_used = parsed.as_of if parsed else None
    # Only a single resolved date is removed; "now" and change questions keep their wording.
    phrase = parsed.matched if parsed and parsed.intent == "point_in_time" else None

    t0 = time.perf_counter()
    hits = search(
        conn, question, as_of_used, embedder=embedder, repo_id=repo_id, top_k=top_k,
        time_filter=temporal,
    )  # fmt: skip
    lap("retrieval", t0)

    t0 = time.perf_counter()
    answer = generate_answer(
        llm, question, hits, as_of=as_of_used, temporal=temporal, time_phrase=phrase
    )
    lap("generation", t0)

    verification = None
    if verify:
        t0 = time.perf_counter()
        answer, verification = verified_answer(
            llm, nli, question, hits, answer, as_of=as_of_used, temporal=temporal,
            time_phrase=phrase, threshold=threshold,
        )  # fmt: skip
        lap("verification", t0)
    return AskResult(question, variant, parsed, hits, answer, timings, verification)
