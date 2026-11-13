"""Labelled time phrases for the temporal parser (plan M5: at least 60).

These check that the rules do what docs/decisions.md says. They are written by hand, so passing
them shows consistency, not real-world accuracy; that is measured on the evaluation questions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.llm import FakeLLM
from app.temporal.parser import explicit, parse_time
from app.temporal.releases import load_prerelease_starts, load_releases

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
R = load_releases()
P = load_prerelease_starts()
US = timedelta(microseconds=1)


def d(y, m=1, day=1):
    return datetime(y, m, day, tzinfo=UTC)


def end_day(y, m, day):
    return d(y, m, day) + timedelta(days=1) - US


def end_month(y, m):
    return (d(y + 1, 1) if m == 12 else d(y, m + 1)) - US


def end_year(y):
    return d(y + 1) - US


def rel(major, minor=0):
    return R[(major, minor)]


def frac(start, end, f):
    return start + (end - start) * f


POINT = [
    # explicit dates
    ("What was the default port on 2023-06-01?", end_day(2023, 6, 1)),
    ("As of 2022/03/15, what did preview.port default to?", end_day(2022, 3, 15)),
    ("What was build.target on June 1, 2023?", end_day(2023, 6, 1)),
    ("What was build.target on 1 June 2023?", end_day(2023, 6, 1)),
    ("What was build.target on the 1st of June, 2023?", end_day(2023, 6, 1)),
    ("Is target es2015 supported in the 2023-05-01 docs?", end_day(2023, 5, 1)),
    # months, quarters, years
    ("What did the docs say in June 2023?", end_month(2023, 6)),
    ("What did the docs say in Jun 2023?", end_month(2023, 6)),
    ("What did the docs say in Sept 2022?", end_month(2022, 9)),
    ("Back in March, 2021, which Node version was required?", end_month(2021, 3)),
    ("What was the default in Q3 2023?", d(2023, 10) - US),
    ("What was the default in q1 2024?", d(2024, 4) - US),
    ("In 2022, what was the default dev server port?", end_year(2022)),
    ("What was json.stringify's default during 2024?", end_year(2024)),
    ("By 2023 what minifier did Vite use?", end_year(2023)),
    ("What was the default port before 2022?", d(2022) - US),
    ("What was the default port prior to June 2022?", d(2022, 6) - US),
    ("What was the default after 2022?", end_year(2022)),
    ("What has been the default since 2023?", d(2023)),
    ("What was the default in early 2023?", frac(d(2023), d(2024), 1 / 6)),
    ("What was the default in mid-2022?", frac(d(2022), d(2023), 1 / 2)),
    ("What was the default in late 2021?", end_year(2021)),
    ("What was the default at the end of 2021?", end_year(2021)),
    ("What was recommended at the start of 2024?", d(2024)),
    ("What did Vite recommend at the beginning of 2022?", d(2022)),
    # Vite versions (dates from the corpus's git tags)
    ("What was the default port before Vite 3?", P[(3, 0)] - US),  # first v3 prerelease
    ("What was the default port in Vite 3?", rel(3)),
    ("What was the default port as of Vite 4.2?", rel(4, 2)),
    ("Which minifier did Vite 2 use?", rel(2)),
    ("How does it work in Vite v6?", rel(6)),
    ("With Vite 7.x what is the default browser target?", rel(7)),
    ("How was SSR configured pre-Vite 4?", P[(4, 0)] - US),
    # relative to NOW (2026-11-13 12:00 UTC)
    ("What was the default a year ago?", d(2025, 11, 13) + timedelta(hours=12)),
    ("What was it 2 years ago?", d(2024, 11, 13) + timedelta(hours=12)),
    ("What did the docs say three months ago?", d(2026, 8, 13) + timedelta(hours=12)),
    ("What was the default two weeks ago?", NOW - timedelta(days=14)),
    ("What was the default last year?", end_year(2025)),
    ("What did it say last month?", end_month(2026, 10)),
    ("What was the default this year?", NOW),
    ("What did the docs say yesterday?", end_day(2026, 11, 12)),
]


@pytest.mark.parametrize(("question", "expected"), POINT, ids=[q for q, _ in POINT])
def test_point_in_time(question, expected):
    p = parse_time(question, NOW, releases=R, prereleases=P)
    assert p.intent == "point_in_time"
    assert p.as_of == expected
    assert p.source == "rules" and not p.assumed


CURRENT = [
    "What is the default port now?",
    "What is the current default port?",
    "Which minifier does Vite use today?",
    "What's the latest Node.js requirement?",
    "Is CJS output still supported?",
    "Nowadays which minifier is the default?",
    "What is the up-to-date default for build.target?",
    "What does server.host default to at the moment?",
]


@pytest.mark.parametrize("question", CURRENT)
def test_current(question):
    p = parse_time(question, NOW, releases=R, prereleases=P)
    assert (p.intent, p.as_of, p.assumed) == ("current", NOW, False)


CHANGE = [
    ("What changed in build.target between 2022 and 2025?", d(2022), end_year(2025)),
    ("How did the default port change from Vite 2 to Vite 3?", rel(2), rel(3)),
    ("What is different between June 2022 and June 2024?", d(2022, 6), end_month(2024, 6)),
    ("What changed since 2024?", d(2024), NOW),
    ("What has changed since Vite 6?", rel(6), NOW),
    ("What changed after Vite 5?", rel(5), NOW),
]


@pytest.mark.parametrize(("question", "start", "as_of"), CHANGE, ids=[c[0] for c in CHANGE])
def test_change(question, start, as_of):
    p = parse_time(question, NOW, releases=R, prereleases=P)
    assert p.intent == "change"
    assert (p.range_start, p.as_of) == (start, as_of)


UNSPECIFIED = [
    "What is the default port of the dev server?",
    "How do I configure the proxy?",
    "Which minifier does Vite use?",
    # numbers that must not be read as dates or versions
    "Why is the build target es2020?",
    "Can I set server.port to 2000?",
    "Does chunkSizeWarningLimit default to 500 kB?",
    "Can I use port 5173 with Vite?",
    "Which Node 18 features does Vite rely on?",
]


@pytest.mark.parametrize("question", UNSPECIFIED)
def test_unspecified_assumes_now(question):
    p = parse_time(question, NOW, releases=R, prereleases=P)
    assert (p.intent, p.as_of, p.assumed, p.source) == ("unspecified", NOW, True, "default")


def test_unknown_version_is_noted_not_guessed():
    p = parse_time("What did Vite 12 add?", NOW, releases=R)
    assert p.intent == "unspecified"
    assert "unknown_version: vite 12" in p.notes


def test_future_dates_are_clamped_and_flagged():
    p = parse_time("What will the default be in 2030?", NOW, releases=R)
    assert p.as_of == NOW and "future_date_clamped" in p.notes


def test_vague_reference_without_llm_falls_back_to_now():
    p = parse_time("What did the docs previously say about the port?", NOW, releases=R)
    assert p.intent == "unspecified" and "vague_time_reference" in p.notes


def test_vague_reference_uses_llm_fallback_when_given():
    llm = FakeLLM(lambda m: '{"date": "2021-05-01", "confidence": 0.7}')
    p = parse_time("What did the docs originally say about the port?", NOW, releases=R, llm=llm)
    assert (p.intent, p.source, p.as_of) == ("point_in_time", "llm", d(2021, 5, 1))
    assert llm.calls[0]["json_mode"] is True


def test_bad_llm_reply_is_ignored():
    llm = FakeLLM(lambda m: "not json")
    p = parse_time("What did the docs originally say?", NOW, releases=R, llm=llm)
    assert p.intent == "unspecified" and p.assumed


def test_llm_is_not_called_when_rules_suffice():
    llm = FakeLLM(lambda m: "{}")
    parse_time("What was the port in 2022?", NOW, releases=R, llm=llm)
    assert llm.calls == []


def test_explicit_as_of_overrides_and_is_clamped():
    assert explicit(d(2023, 1, 1), NOW).as_of == d(2023, 1, 1)
    assert explicit(datetime(2023, 1, 1), NOW).as_of == d(2023, 1, 1)  # naive -> UTC
    future = explicit(d(2030), NOW)
    assert future.as_of == NOW and "future_date_clamped" in future.notes


def test_labelled_set_has_at_least_60_phrases():
    assert len(POINT) + len(CURRENT) + len(CHANGE) + len(UNSPECIFIED) >= 60


def test_before_a_version_means_before_its_first_prerelease():
    p = parse_time(
        "Which Node.js version did Vite require before Vite 3?", NOW, releases=R, prereleases=P
    )
    assert p.as_of < R[(3, 0)] and p.as_of == P[(3, 0)] - US
    assert p.as_of.date().isoformat() == "2022-05-13"
