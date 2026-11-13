"""Generate candidate evaluation questions from fact timelines (plan section 10).

Question types:
- point_in_time: "What was the default value of `build.minify` in June 2023?"
- current:       "What is the default value of `build.minify` now?"
- unanswerable:  asked about a date before the option was documented at all; correct = NOT_FOUND
- change:        "How did the default value of X change between June 2022 and March 2025?"

Dates are chosen at least `MARGIN` inside a span so the answer is not ambiguous around a
change, and the as-of instant is computed here independently of app/temporal/parser.py using
the conventions in docs/decisions.md (tests check both agree).

Everything is deterministic for a given seed. Candidates are reviewed by a person before use.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from app.evaluation.facts import Fact, Span, contains_token, key_tokens
from app.temporal.releases import Releases

GENERATOR_VERSION = "questions-v1"
MARGIN = timedelta(days=14)
MIN_SPAN = timedelta(days=60)
CORPUS_START = datetime(2021, 3, 1, tzinfo=UTC)  # first months of history are too sparse
_US = timedelta(microseconds=1)
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]  # fmt: skip


@dataclass
class Question:
    id: str
    fact_key: str
    type: str
    question: str
    as_of: str
    now: str
    answerable: bool
    gold_answer: str
    gold_tokens: list[str]
    stale_tokens: list[str]
    gold_refs: list[dict]
    split: str
    range_start: str | None = None
    time_phrase: str | None = None
    flags: list[str] = field(default_factory=list)
    reviewed: bool = False
    generator: str = GENERATOR_VERSION

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------- time phrases
def _end_month(y: int, m: int) -> datetime:
    return (
        datetime(y + 1, 1, 1, tzinfo=UTC) if m == 12 else datetime(y, m + 1, 1, tzinfo=UTC)
    ) - _US


def _end_year(y: int) -> datetime:
    return datetime(y + 1, 1, 1, tzinfo=UTC) - _US


def _end_day(d: datetime) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1) - _US


def _inside(t: datetime, lo: datetime, hi: datetime) -> bool:
    return lo <= t <= hi


def phrase_options(
    span: Span, now: datetime, releases: Releases, prereleases: Releases, rng: random.Random
) -> list[tuple[str, datetime]]:
    """(phrase, as_of) pairs whose as-of lies safely inside the span."""
    start = max(span.start, CORPUS_START)
    end = span.end or now
    lo, hi = start + MARGIN, end - MARGIN
    if hi - lo < MIN_SPAN - 2 * MARGIN:
        return []
    out: list[tuple[str, datetime]] = []

    months = []
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        if _inside(_end_month(y, m), lo, hi):
            months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if months:
        y, m = rng.choice(months)
        word = rng.choice(["in", "as of"])
        out.append((f"{word} {_MONTHS[m - 1]} {y}", _end_month(y, m)))

    years = [y for y in range(lo.year, hi.year + 1) if _inside(_end_year(y), lo, hi)]
    if years:
        y = rng.choice(years)
        out.append((rng.choice([f"in {y}", f"at the end of {y}"]), _end_year(y)))

    day = lo + (hi - lo) * rng.uniform(0.2, 0.8)
    out.append((f"on {_MONTHS[day.month - 1]} {day.day}, {day.year}", _end_day(day)))

    for (major, minor), when in sorted(releases.items()):
        if minor == 0 and _inside(when, start + timedelta(days=7), hi):
            out.append((f"in Vite {major}", when))
        before = prereleases.get((major, minor), when) - _US
        if minor == 0 and _inside(before, lo, end - _US):
            out.append((f"before Vite {major}", before))
    return out


# ---------------------------------------------------------------------------- templates
_PAST = [
    "What was the default value of `{s}` {p}?",
    "{P}, what did `{s}` default to?",
    "Which default did `{s}` have {p}?",
]
_CURRENT = [
    "What is the default value of `{s}` now?",
    "What does `{s}` currently default to?",
    "What is the current default for `{s}`?",
]
_NODE_PAST = [
    "Which Node.js version did Vite require {p}?",
    "{P}, which Node.js versions did Vite support?",
]
_NODE_CURRENT = [
    "Which Node.js version does Vite require now?",
    "Which Node.js versions does Vite currently support?",
]
_CHANGE = "How did the default value of `{s}` change between {a} and {b}?"
_NODE_CHANGE = "How did Vite's required Node.js version change between {a} and {b}?"


def _fill(template: str, subject: str, phrase: str = "") -> str:
    return template.format(s=subject, p=phrase, P=phrase[:1].upper() + phrase[1:])


def checkable(fact: Fact) -> list[str]:
    """Reasons a fact's values cannot be checked by token matching (empty = fine)."""
    reasons = []
    for span in fact.spans:
        if len(span.core) > 45 or any(x in span.core for x in ("=>", "/^", "{", "*.")):
            reasons.append(f"complex value: {span.core[:30]}")
    return reasons


def _split(fact_key: str) -> str:
    digest = int(hashlib.sha256(fact_key.encode()).hexdigest(), 16)
    return "test" if digest % 10 < 3 else "dev"  # ~30% held out, grouped by fact


def _ref(span: Span, when: datetime) -> dict:
    seg = span.segment_at(when) or span.segments[-1]
    return {
        "source_path": seg.source_path,
        "section_path": seg.section_path,
        "chunk_id": seg.chunk_id,
    }


def _stale(fact: Fact, gold_span: Span) -> list[str]:
    """Tokens of values valid at other times, minus any the gold default text itself mentions
    (e.g. "'lightningcss', but false if build.minify is disabled" must not make build.minify
    a stale token)."""
    gold_tokens = {t.lower() for t in key_tokens(gold_span.core)}
    stale: list[str] = []
    for span in fact.spans:
        if span.core != gold_span.core:
            stale += [t for t in key_tokens(span.core) if t.lower() not in gold_tokens]
    stale = [t for t in stale if not contains_token(gold_span.raw, t)]
    return list(dict.fromkeys(stale))


def _flags(gold: str, stale: list[str], fact: Fact) -> list[str]:
    flags = []
    if fact.changed and not stale:
        flags.append("stale_undetectable")
    if gold.lower() in ("true", "false", "undefined", "0", "[]"):
        flags.append("short_value")
    return flags


def generate(
    facts: list[Fact],
    now: datetime,
    releases: Releases,
    prereleases: Releases,
    seed: int = 7,
) -> list[Question]:
    rng = random.Random(seed)
    out: list[Question] = []
    now_iso = now.isoformat()

    def add(fact: Fact, qtype: str, text: str, as_of: datetime, **kw) -> None:
        qid = hashlib.sha1(f"{fact.key}|{qtype}|{text}".encode()).hexdigest()[:10]
        out.append(
            Question(
                id=f"q_{qid}",
                fact_key=fact.key,
                type=qtype,
                question=text,
                as_of=as_of.isoformat(),
                now=now_iso,
                split=_split(fact.key),
                **kw,
            )
        )

    for fact in facts:
        if checkable(fact):
            continue
        node = fact.kind == "node_requirement"
        past, current = (_NODE_PAST, _NODE_CURRENT) if node else (_PAST, _CURRENT)

        # point in time: one or two per span, preferring spans of changed facts
        if fact.changed:
            for span in fact.spans:
                options = phrase_options(span, now, releases, prereleases, rng)
                rng.shuffle(options)
                for phrase, as_of in options[:2]:
                    stale = _stale(fact, span)
                    add(fact, "point_in_time", _fill(rng.choice(past), fact.subject, phrase), as_of,
                        answerable=True, gold_answer=span.core, gold_tokens=key_tokens(span.core),
                        stale_tokens=stale, gold_refs=[_ref(span, as_of)], time_phrase=phrase,
                        flags=_flags(span.core, stale, fact))  # fmt: skip

        # current
        last = fact.spans[-1]
        if last.end is None and now - last.start >= timedelta(days=30):
            stale = _stale(fact, last)
            add(fact, "current", _fill(rng.choice(current), fact.subject), now,
                answerable=True, gold_answer=last.core, gold_tokens=key_tokens(last.core),
                stale_tokens=stale, gold_refs=[_ref(last, now)], time_phrase="now",
                flags=_flags(last.core, stale, fact))  # fmt: skip

        # unanswerable: a month well before the option was documented at all
        if not node and fact.first_seen - CORPUS_START >= timedelta(days=120):
            latest = fact.first_seen - timedelta(days=60)
            months = []
            y, m = CORPUS_START.year, CORPUS_START.month
            while _end_month(y, m) <= latest:
                months.append((y, m))
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            if months:
                y, m = rng.choice(months)
                phrase = f"in {_MONTHS[m - 1]} {y}"
                add(fact, "unanswerable", _fill(rng.choice(past), fact.subject, phrase),
                    _end_month(y, m), answerable=False, gold_answer="NOT_FOUND", gold_tokens=[],
                    stale_tokens=[], gold_refs=[], time_phrase=phrase,
                    flags=["verify_not_documented_elsewhere"])  # fmt: skip

        # change: two months fully inside two spans with different values
        if fact.changed:
            spans = [
                s for s in fact.spans if (s.end or now) - max(s.start, CORPUS_START) >= MIN_SPAN
            ]
            pairs = [
                (a, b) for i, a in enumerate(spans) for b in spans[i + 1 :] if a.core != b.core
            ]
            if pairs:
                a, b = rng.choice(pairs)
                pa = phrase_options(a, now, releases, prereleases, rng)
                pb = phrase_options(b, now, releases, prereleases, rng)

                def whole_period_inside(span, options):
                    # the "from" period must lie entirely inside its span, not just end there
                    lo = max(span.start, CORPUS_START) + MARGIN
                    return [
                        (p, t) for p, t in options
                        if p.startswith(("in ", "as of ")) and "Vite" not in p
                        and _start_of(p.split(" ", 1)[1].replace("of ", "")) >= lo
                    ]  # fmt: skip

                ma = whole_period_inside(a, pa)
                mb = whole_period_inside(b, pb)
                if ma and mb:
                    (p1, _), (p2, t2) = ma[0], mb[0]
                    p1, p2 = (
                        p1.split(" ", 1)[1].replace("of ", ""),
                        p2.split(" ", 1)[1].replace("of ", ""),
                    )
                    template = _NODE_CHANGE if node else _CHANGE
                    first_start = _start_of(p1)
                    add(fact, "change", template.format(s=fact.subject, a=p1, b=p2), t2,
                        answerable=True, gold_answer=f"from {a.core} to {b.core}",
                        gold_tokens=list(dict.fromkeys(key_tokens(a.core) + key_tokens(b.core))),
                        stale_tokens=[], gold_refs=[_ref(a, first_start), _ref(b, t2)],
                        range_start=first_start.isoformat(), time_phrase=f"between {p1} and {p2}",
                        flags=["change_question"])  # fmt: skip
    return out


def _start_of(period: str) -> datetime:
    """Start of "June 2023" or "2023" (used for change questions' range start)."""
    parts = period.split()
    if len(parts) == 2:
        return datetime(int(parts[1]), _MONTHS.index(parts[0]) + 1, 1, tzinfo=UTC)
    return datetime(int(parts[0]), 1, 1, tzinfo=UTC)
