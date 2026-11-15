"""Verify each claim against its cited sources, label it, and decide what to do (plan M7, M8).

Labels (project_plan.md appendix B):
  supported_current   entailed by a cited source that is valid on the as-of date
  supported_outdated  entailed only by cited sources that are NOT valid on the as-of date
  unsupported         not entailed by any cited source (or nothing cited)

Policy:
  every claim supported_current  -> keep the answer
  otherwise, revision allowed    -> ask the model once to rewrite using only supported facts
  still not all supported        -> keep only the supported claims (with their citations)
  no supported claim left        -> abstain (NOT_FOUND)

Without an as-of date (the plain variant) only entailment is checked, so nothing can be
labelled outdated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.core.llm import LLMClient
from app.generation.answer import NOT_FOUND, Answer, generate_answer, parse_answer
from app.retrieval.search import Hit
from app.verification.claims import Claim, extract_claims
from app.verification.nli import NLIModel, entailment_against_chunk

DEFAULT_THRESHOLD = 0.5  # calibrated on hand-labelled claims in Week 8


@dataclass
class ClaimVerdict:
    text: str
    sources: list[str]
    entailment: float
    contradiction: float
    best_source: str | None
    best_chunk_id: int | None
    best_valid_from: str | None
    best_valid_until: str | None
    valid_at_as_of: bool | None
    label: str


@dataclass
class Verification:
    verdicts: list[ClaimVerdict]
    action: str  # keep | revised | dropped_claims | abstained | nothing_to_verify
    original_answer: str
    extraction_method: str
    revised_verdicts: list[ClaimVerdict] = field(default_factory=list)
    extra_llm_calls: int = 0

    def to_json(self) -> dict:
        return asdict(self)


def _valid(hit: Hit, as_of: datetime) -> bool:
    return hit.valid_from <= as_of and (hit.valid_until is None or as_of < hit.valid_until)


def _uncited(claim: Claim) -> ClaimVerdict:
    return ClaimVerdict(
        text=claim.text,
        sources=claim.sources,
        entailment=0.0,
        contradiction=0.0,
        best_source=None,
        best_chunk_id=None,
        best_valid_from=None,
        best_valid_until=None,
        valid_at_as_of=None,
        label="unsupported",
    )


def verify_claims(
    claims: list[Claim],
    hits: list[Hit],
    nli: NLIModel,
    as_of: datetime | None,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[ClaimVerdict]:
    by_label = {f"S{i}": h for i, h in enumerate(hits, start=1)}
    # score every claim against every chunk it cites, one model call per chunk
    scores: dict[tuple[int, str], dict] = {}
    for label, hit in by_label.items():
        idx = [i for i, c in enumerate(claims) if label in c.sources]
        if not idx:
            continue
        premise = f"{hit.section_path}\n\n{hit.text}"
        for i, s in zip(
            idx, entailment_against_chunk(nli, premise, [claims[i].text for i in idx]), strict=True
        ):
            scores[(i, label)] = s

    verdicts = []
    for i, claim in enumerate(claims):
        cited = [(lab, scores[(i, lab)]) for lab in claim.sources if (i, lab) in scores]
        if not cited:
            verdicts.append(_uncited(claim))
            continue
        entailed = [(lab, s) for lab, s in cited if s.get("entailment", 0) >= threshold]
        if as_of is not None:
            current = [(lab, s) for lab, s in entailed if _valid(by_label[lab], as_of)]
        else:
            current = entailed
        pool = current or entailed or cited
        lab, s = max(pool, key=lambda x: x[1].get("entailment", 0))
        hit = by_label[lab]
        valid = _valid(hit, as_of) if as_of is not None else None
        if current:
            label = "supported_current"
        elif entailed:
            label = "supported_outdated"
        else:
            label = "unsupported"
        verdicts.append(
            ClaimVerdict(
                text=claim.text,
                sources=claim.sources,
                entailment=round(s.get("entailment", 0.0), 4),
                contradiction=round(s.get("contradiction", 0.0), 4),
                best_source=lab,
                best_chunk_id=hit.chunk_id,
                best_valid_from=hit.valid_from.isoformat(),
                best_valid_until=hit.valid_until.isoformat() if hit.valid_until else None,
                valid_at_as_of=valid,
                label=label,
            )
        )
    return verdicts


_REVISE = (
    "Your previous answer contained statements that are not supported by the cited sources{when}:\n"
    "{problems}\n"
    "Answer the question again using only statements that the sources support, citing them as "
    "before. If the sources do not contain the answer, reply with exactly: NOT_FOUND"
)


def _problems(verdicts: list[ClaimVerdict]) -> str:
    lines = []
    for v in verdicts:
        if v.label == "unsupported":
            lines.append(f'- "{v.text}" (not supported by {", ".join(v.sources) or "any source"})')
        elif v.label == "supported_outdated":
            lines.append(f'- "{v.text}" (its source was not valid on the date asked about)')
    return "\n".join(lines)


def _from_supported(verdicts: list[ClaimVerdict]) -> str:
    kept = [v for v in verdicts if v.label == "supported_current"]
    return " ".join(f"{v.text.rstrip('.')}. [{v.best_source}]" for v in kept)


def verified_answer(
    llm: LLMClient,
    nli: NLIModel,
    question: str,
    hits: list[Hit],
    answer: Answer,
    *,
    as_of: datetime | None,
    temporal: bool,
    time_phrase: str | None,
    threshold: float = DEFAULT_THRESHOLD,
    allow_revision: bool = True,
) -> tuple[Answer, Verification]:
    """Check `answer`; return the final answer (possibly revised or reduced) and the record."""
    if answer.not_found or not hits:
        return answer, Verification([], "nothing_to_verify", answer.text, "none")

    extraction = extract_claims(llm, answer.text)
    calls = 1 if extraction.method != "sentence_fallback" else 2
    verdicts = verify_claims(extraction.claims, hits, nli, as_of, threshold)
    record = Verification(verdicts, "keep", answer.text, extraction.method, extra_llm_calls=calls)
    if verdicts and all(v.label == "supported_current" for v in verdicts):
        return answer, record

    if allow_revision and verdicts:
        when = f" on {as_of.date().isoformat()}" if as_of is not None else ""
        feedback = _REVISE.format(when=when, problems=_problems(verdicts))
        revised = generate_answer(
            llm, question, hits, as_of=as_of, temporal=temporal, time_phrase=time_phrase,
            previous_answer=answer.text, feedback=feedback,
        )  # fmt: skip
        record.extra_llm_calls += 1
        if revised.not_found:
            record.action = "abstained"
            return revised, record
        re_extraction = extract_claims(llm, revised.text)
        record.extra_llm_calls += 1
        record.revised_verdicts = verify_claims(re_extraction.claims, hits, nli, as_of, threshold)
        if record.revised_verdicts and all(
            v.label == "supported_current" for v in record.revised_verdicts
        ):
            record.action = "revised"
            return revised, record
        verdicts = record.revised_verdicts or verdicts

    text = _from_supported(verdicts)
    if not text:
        record.action = "abstained"
        return Answer(NOT_FOUND, not_found=True, model=answer.model), record
    record.action = "dropped_claims"
    not_found, cited, invalid, uncited = parse_answer(text, hits)
    return (
        Answer(text, not_found, cited, invalid, uncited, model=answer.model,
               prompt_version=answer.prompt_version),
        record,
    )  # fmt: skip
