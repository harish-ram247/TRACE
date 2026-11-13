"""Work out which point in time a question is about.

Output is a `TimeParse` with an `as_of` instant that retrieval filters on, plus the intent:

- point_in_time  "What was the default port in June 2023?"
- current        "What is the default port now?"
- change         "What changed in build.target between 2022 and 2025?" (as_of = later end,
                 range_start = earlier one; answering change questions is a stretch goal)
- unspecified    no time reference: `as_of` = now and `assumed` = True, so the answer can say
                 which date it assumed

Rules first, in this order: change phrasing, Vite versions ("before Vite 3"), explicit dates
("2023-06-01", "June 2023", "Q3 2023", "2023"), relative phrases ("last year", "2 years ago"),
then "current" words. Only if nothing matches but the question sounds time-related
("previously", "used to"), an optional LLM fallback is asked for a date.

How a period maps to an instant (documented in docs/decisions.md):
- "in / as of / during / by / at P" -> end of P (the latest state within P)
- "before / prior to P"              -> just before the start of P
- "after P"                          -> end of P
- "since / from P"                   -> start of P
- "early / mid / late P"             -> 1/6, 1/2, end of P
Instants later than `now` are clamped to `now`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.core.llm import LLMClient, LLMError
from app.temporal.releases import Releases, load_prerelease_starts, load_releases

Intent = Literal["point_in_time", "current", "change", "unspecified"]
Source = Literal["explicit", "rules", "llm", "default"]

_US = timedelta(microseconds=1)


@dataclass(frozen=True)
class TimeParse:
    as_of: datetime
    intent: Intent
    confidence: float
    source: Source
    matched: str | None = None
    assumed: bool = False
    range_start: datetime | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _Ref:
    start: datetime
    end: datetime  # exclusive end of the period; equals start for a point (a release)
    span: tuple[int, int]
    text: str
    qualifier: str
    confidence: float


# ---------------------------------------------------------------------------- calendar helpers
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_MONTH_RE = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
)
_YEAR_RE = r"((?:19|20)\d{2})"


def _dt(y: int, m: int = 1, d: int = 1) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


def _add_months(y: int, m: int, n: int) -> tuple[int, int]:
    total = y * 12 + (m - 1) + n
    return total // 12, total % 12 + 1


def _month_period(y: int, m: int) -> tuple[datetime, datetime]:
    ny, nm = _add_months(y, m, 1)
    return _dt(y, m), _dt(ny, nm)


def _year_period(y: int) -> tuple[datetime, datetime]:
    return _dt(y), _dt(y + 1)


# ---------------------------------------------------------------------------- qualifiers
_QUALIFIER = re.compile(
    r"(before|prior to|pre-|until|till|up to|after|since|from|as of|as at|in|during|on|at|by"
    r"|around|early|mid-?|late|end of|the end of|start of|beginning of|the start of)\s*$"
)


def _qualifier(text: str, start: int) -> str:
    window = text[max(0, start - 20) : start].lower()
    m = _QUALIFIER.search(window)
    if not m:
        return ""
    q = m.group(1).rstrip("-").replace("the ", "")
    return {"prior to": "before", "pre": "before", "as at": "as of"}.get(q, q)


def _resolve(ref: _Ref, now: datetime) -> datetime:
    q, s, e = ref.qualifier, ref.start, ref.end
    if s == e:  # a point (release date)
        point = s - _US if q in ("before", "until", "till", "up to") else s
    elif q in ("before",):
        point = s - _US
    elif q in ("since", "from", "start of", "beginning of"):
        point = s
    elif q == "early":
        point = s + (e - s) / 6
    elif q == "mid":
        point = s + (e - s) / 2
    else:  # in, as of, during, by, at, on, after, until, late, end of, around, none
        point = e - _US
    return min(point, now)


# ---------------------------------------------------------------------------- reference finders
def _find_dates(text: str) -> list[_Ref]:
    refs: list[_Ref] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    def add(a, b, start, end, conf):
        if free(a, b):
            taken.append((a, b))
            refs.append(_Ref(start, end, (a, b), text[a:b], _qualifier(text, a), conf))

    low = text.lower()
    for m in re.finditer(r"\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", low):
        y, mo, d = (int(g) for g in m.groups())
        try:
            day = _dt(y, mo, d)
        except ValueError:
            continue
        add(m.start(), m.end(), day, day + timedelta(days=1), 0.95)
    for m in re.finditer(rf"\b{_MONTH_RE}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR_RE}\b", low):
        mo, d, y = _MONTHS[m.group(1)[:3]], int(m.group(2)), int(m.group(3))
        try:
            day = _dt(y, mo, d)
        except ValueError:
            continue
        add(m.start(), m.end(), day, day + timedelta(days=1), 0.95)
    for m in re.finditer(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH_RE},?\s+{_YEAR_RE}\b", low
    ):
        d, mo, y = int(m.group(1)), _MONTHS[m.group(2)[:3]], int(m.group(3))
        try:
            day = _dt(y, mo, d)
        except ValueError:
            continue
        add(m.start(), m.end(), day, day + timedelta(days=1), 0.95)
    for m in re.finditer(rf"\b{_MONTH_RE},?\s+(?:of\s+)?{_YEAR_RE}\b", low):
        add(m.start(), m.end(), *_month_period(int(m.group(2)), _MONTHS[m.group(1)[:3]]), 0.9)
    for m in re.finditer(rf"\bq([1-4])\s*{_YEAR_RE}\b", low):
        q, y = int(m.group(1)), int(m.group(2))
        start = _dt(y, 3 * q - 2)
        ny, nm = _add_months(y, 3 * q - 2, 3)
        add(m.start(), m.end(), start, _dt(ny, nm), 0.9)
    # Bare years: only 2010-2039 (Vite exists since 2020), so numbers like "2000 ms" are not dates.
    for m in re.finditer(r"(?<![\w.@/])(?<!\d-)(20[1-3]\d)(?![\w.-]|\s*-\s*\d)", low):
        add(m.start(), m.end(), *_year_period(int(m.group(1))), 0.8)
    return refs


def _find_relative(text: str, now: datetime) -> list[_Ref]:
    low, refs = text.lower(), []
    words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    for m in re.finditer(
        r"\b(\d+|a|an|one|two|three|four|five|six)\s+(year|month|week|day)s?\s+ago\b", low
    ):
        n = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1)]
        unit = m.group(2)
        if unit == "year":
            point = now.replace(
                year=now.year - n, day=min(now.day, 28) if now.month == 2 else now.day
            )
        elif unit == "month":
            y, mo = _add_months(now.year, now.month, -n)
            point = now.replace(year=y, month=mo, day=min(now.day, 28))
        else:
            point = now - timedelta(days=n * (7 if unit == "week" else 1))
        refs.append(_Ref(point, point, m.span(), m.group(0), _qualifier(text, m.start()), 0.8))
    for m in re.finditer(r"\b(last|this|previous)\s+(year|month)\b", low):
        this = m.group(1) == "this"
        if m.group(2) == "year":
            start, end = _year_period(now.year if this else now.year - 1)
        else:
            y, mo = (now.year, now.month) if this else _add_months(now.year, now.month, -1)
            start, end = _month_period(y, mo)
        refs.append(_Ref(start, end, m.span(), m.group(0), _qualifier(text, m.start()), 0.8))
    if m := re.search(r"\byesterday\b", low):
        day = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=1)
        refs.append(_Ref(day, day + timedelta(days=1), m.span(), m.group(0), "", 0.85))
    return refs


def _find_versions(
    text: str, releases: Releases, prereleases: Releases
) -> tuple[list[_Ref], list[str]]:
    """Version mentions. "before Vite N" uses N's first prerelease: the docs on the main branch
    already describe N during its alpha/beta (verified on Vite 3, docs/devlog.md)."""
    refs, notes = [], []
    for m in re.finditer(r"\bvite\s*v?(\d+)(?:\.(\d+))?(?:\.x|\.\d+)?\b", text.lower()):
        major, minor = int(m.group(1)), int(m.group(2) or 0)
        key = (major, minor) if (major, minor) in releases else (major, 0)
        if key not in releases:
            notes.append(f"unknown_version: {m.group(0)}")
            continue
        qualifier = _qualifier(text, m.start())
        when = releases[key]
        if qualifier in ("before", "until", "till", "up to"):
            when = prereleases.get(key, when)
        refs.append(_Ref(when, when, m.span(), m.group(0), qualifier, 0.85))
    return refs, notes


_CURRENT = re.compile(
    r"\b(now|currently|current|today|latest|nowadays|these days|at present|presently"
    r"|at the moment|right now|up[- ]to[- ]date|still)\b"
)
_CHANGE = re.compile(r"\b(change[sd]?|changing|differen(?:ce|t)|evolve[sd]?|new since|between)\b")
_VAGUE = re.compile(
    r"\b(previously|originally|initially|used to|back (?:then|when)|in the past|earlier"
    r"|old(?:er)? (?:docs|documentation|versions?)|at first|formerly|before)\b"
)


# ---------------------------------------------------------------------------- LLM fallback
_LLM_SYSTEM = (
    "You map a question about the Vite documentation to the date it refers to. "
    'Reply with a JSON object only: {"date": "YYYY-MM-DD" or null, "confidence": 0 to 1}. '
    "Use null if the question does not refer to a specific time."
)


def _llm_date(llm: LLMClient, question: str, now: datetime, releases: Releases) -> datetime | None:
    majors = ", ".join(
        f"Vite {ma}: {d.date()}" for (ma, mi), d in sorted(releases.items()) if mi == 0
    )
    user = f"Today is {now.date()}. Release dates: {majors}.\nQuestion: {question}"
    try:
        reply = llm.complete(
            [{"role": "system", "content": _LLM_SYSTEM}, {"role": "user", "content": user}],
            max_tokens=60,
            json_mode=True,
        )
        data = json.loads(reply.text)
        if not data.get("date"):
            return None
        return datetime.fromisoformat(data["date"]).replace(tzinfo=UTC)
    except (LLMError, ValueError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------- entry point
def parse_time(
    question: str,
    now: datetime | None = None,
    *,
    releases: Releases | None = None,
    prereleases: Releases | None = None,
    llm: LLMClient | None = None,
) -> TimeParse:
    now = now or datetime.now(UTC)
    releases = load_releases() if releases is None else releases
    prereleases = load_prerelease_starts() if prereleases is None else prereleases
    version_refs, notes = _find_versions(question, releases, prereleases)
    refs = sorted(version_refs + _find_dates(question) + _find_relative(question, now),
                  key=lambda r: r.span[0])  # fmt: skip
    notes_t = tuple(notes)

    if refs:
        future = [r for r in refs if r.start > now]
        if future:
            notes_t += ("future_date_clamped",)
        if len(refs) >= 2 and _CHANGE.search(question.lower()):
            first, last = refs[0], refs[-1]
            as_since = _Ref(first.start, first.end, first.span, first.text, "since", 1)
            start = _resolve(as_since, now)
            return TimeParse(
                as_of=_resolve(last, now),
                intent="change",
                confidence=min(first.confidence, last.confidence),
                source="rules",
                matched=f"{first.text} .. {last.text}",
                range_start=start,
                notes=notes_t,
            )
        ref = refs[-1] if len(refs) > 1 else refs[0]
        if ref.qualifier in ("since", "from", "after") and _CHANGE.search(question.lower()):
            return TimeParse(now, "change", ref.confidence, "rules", ref.text,
                             range_start=_resolve(ref, now), notes=notes_t)  # fmt: skip
        if len(refs) > 1:
            notes_t += ("multiple_time_references",)
        return TimeParse(_resolve(ref, now), "point_in_time", ref.confidence, "rules", ref.text,
                         notes=notes_t)  # fmt: skip

    if m := _CURRENT.search(question.lower()):
        return TimeParse(now, "current", 0.9, "rules", m.group(0), notes=notes_t)

    if _VAGUE.search(question.lower()):
        notes_t += ("vague_time_reference",)
        if llm is not None and (when := _llm_date(llm, question, now, releases)) is not None:
            return TimeParse(min(when, now), "point_in_time", 0.6, "llm", None, notes=notes_t)

    return TimeParse(now, "unspecified", 0.5, "default", None, assumed=True, notes=notes_t)


def explicit(as_of: datetime, now: datetime | None = None) -> TimeParse:
    """An as-of date given by the caller overrides parsing."""
    now = now or datetime.now(UTC)
    as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    notes = ("future_date_clamped",) if as_of > now else ()
    return TimeParse(min(as_of, now), "point_in_time", 1.0, "explicit", None, notes=notes)
