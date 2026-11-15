"""POST /ask: answer a question about the documentation as of a point in time.

Rate limited per client (see app/api/ratelimit.py). Verified variants also return each claim's
verdict. The NLI model is only loaded when a verified variant is asked for.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.ratelimit import rate_limited
from app.core.config import get_settings
from app.core.llm import LLMClient, LLMError, get_llm
from app.core.pg import get_conn
from app.pipeline import ask
from app.retrieval.embeddings import Embedder, get_embedder
from app.verification.nli import NLIModel, get_nli

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of: datetime | None = Field(
        default=None, description="Overrides the date parsed from the question"
    )
    variant: Literal["temporal", "plain", "temporal_verified", "plain_verified"] = "temporal"
    top_k: int = Field(default=5, ge=1, le=10)


class TimeInfo(BaseModel):
    as_of: datetime
    intent: str
    confidence: float
    source: str
    matched: str | None
    assumed: bool
    range_start: datetime | None
    notes: list[str]


class Source(BaseModel):
    label: str
    chunk_id: int
    source_path: str
    section_path: str
    valid_from: datetime
    valid_until: datetime | None
    text: str


class ClaimOut(BaseModel):
    text: str
    sources: list[str]
    label: str
    entailment: float
    valid_at_as_of: bool | None


class VerificationOut(BaseModel):
    action: str
    original_answer: str
    claims: list[ClaimOut]
    revised_claims: list[ClaimOut]


class AskResponse(BaseModel):
    question: str
    variant: str
    time: TimeInfo | None
    answer: str
    not_found: bool
    cited_labels: list[str]
    invalid_citations: list[str]
    uncited: bool
    sources: list[Source]
    model: str | None
    prompt_version: str
    cached: bool
    timings_ms: dict[str, int]
    verification: VerificationOut | None = None


def embedder_dep() -> Embedder:
    return get_embedder()


def llm_dep() -> LLMClient:
    return get_llm()


def nli_dep() -> Callable[[], NLIModel]:
    return get_nli  # called only for verified variants


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(rate_limited)])
def ask_endpoint(
    req: AskRequest,
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
    embedder: Annotated[Embedder, Depends(embedder_dep)],
    llm: Annotated[LLMClient, Depends(llm_dep)],
    nli: Annotated[Callable[[], NLIModel], Depends(nli_dep)],
) -> AskResponse:
    try:
        result = ask(
            conn,
            req.question,
            embedder=embedder,
            llm=llm,
            repo_id=get_settings().corpus_repo_id,
            variant=req.variant,
            as_of=req.as_of,
            top_k=req.top_k,
            nli=nli() if req.variant.endswith("_verified") else None,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"language model error: {exc}") from exc

    t = result.time
    return AskResponse(
        question=result.question,
        variant=result.variant,
        time=TimeInfo(
            as_of=t.as_of,
            intent=t.intent,
            confidence=t.confidence,
            source=t.source,
            matched=t.matched,
            assumed=t.assumed,
            range_start=t.range_start,
            notes=list(t.notes),
        )
        if t
        else None,
        answer=result.answer.text,
        not_found=result.answer.not_found,
        cited_labels=[c.label for c in result.answer.citations],
        invalid_citations=result.answer.invalid_citations,
        uncited=result.answer.uncited,
        sources=[
            Source(
                label=f"S{i}",
                chunk_id=h.chunk_id,
                source_path=h.source_path,
                section_path=h.section_path,
                valid_from=h.valid_from,
                valid_until=h.valid_until,
                text=h.text,
            )
            for i, h in enumerate(result.hits, start=1)
        ],
        model=result.answer.model,
        prompt_version=result.answer.prompt_version,
        cached=result.answer.cached,
        timings_ms=result.timings_ms,
        verification=_verification(result.verification),
    )


def _claims(verdicts) -> list[ClaimOut]:
    return [
        ClaimOut(text=v.text, sources=v.sources, label=v.label, entailment=v.entailment,
                 valid_at_as_of=v.valid_at_as_of)
        for v in verdicts
    ]  # fmt: skip


def _verification(v) -> VerificationOut | None:
    if v is None:
        return None
    return VerificationOut(
        action=v.action,
        original_answer=v.original_answer,
        claims=_claims(v.verdicts),
        revised_claims=_claims(v.revised_verdicts),
    )
