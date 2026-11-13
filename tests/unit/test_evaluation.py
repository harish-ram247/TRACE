import random
from datetime import UTC, datetime, timedelta

from app.evaluation.facts import (
    Fact,
    Segment,
    Span,
    _merge,
    check_answer,
    contains_token,
    core_value,
    key_tokens,
)
from app.evaluation.questions import checkable, generate, phrase_options
from app.temporal.parser import parse_time
from app.temporal.releases import load_prerelease_starts, load_releases

R, P = load_releases(), load_prerelease_starts()
NOW = datetime(2026, 11, 13, tzinfo=UTC)


def d(y, m=1, day=1):
    return datetime(y, m, day, tzinfo=UTC)


# ---- core values and tokens --------------------------------------------------------------
def test_core_value_ignores_cosmetics():
    assert core_value("`4096` (4kb)") == core_value("`4096` (4 KiB)") == "4096"
    assert core_value("`'esbuild'` for client build, `false` for SSR build") == "esbuild"
    assert core_value("[`server.cors`](#server_proxy)") == core_value(
        "[`server.cors`](./server-options#server-cors)"
    )
    assert core_value("`'iife'`") == core_value("`iife`") == "iife"


def test_key_tokens():
    assert key_tokens("['.mjs', '.js', '.mts']") == [".mjs", ".js", ".mts"]
    assert key_tokens("20.19+, 22.12+") == ["20.19", "22.12"]
    assert key_tokens(">=14.18.0") == ["14.18"]
    assert key_tokens("18+ or 20+") == ["18", "20"]
    assert key_tokens("baseline-widely-available") == ["baseline-widely-available"]


def test_contains_token_respects_boundaries():
    assert contains_token("Vite requires Node.js 14.18.0 or later", "14.18")
    assert contains_token("Node 14.18+ and 16+", "16")
    assert not contains_token("Node 12.2.0", "12")
    assert not contains_token("it is automatically enabled", "auto")
    assert contains_token("The default is `'auto'`.", "auto")
    assert not contains_token("5173", "517")


def test_check_answer():
    assert check_answer("The default was `'esbuild'` [S1].", ["esbuild"], ["terser", "oxc"])
    assert not check_answer("It changed from terser to esbuild.", ["esbuild"], ["terser"])
    assert not check_answer("NOT_FOUND", ["esbuild"], [])
    assert check_answer("NOT_FOUND", [], [], answerable=False)
    assert not check_answer("It was 5173.", [], [], answerable=False)


# ---- timelines ---------------------------------------------------------------------------
def seg(start, end, core):
    return Segment(start, end, f"`{core}`", core, "docs/config/x.md", "X > opt", 1)


def test_merge_joins_contiguous_equal_values_only():
    spans = _merge(
        [seg(d(2021), d(2022), "a"), seg(d(2022), d(2023), "a"), seg(d(2023), None, "b")]
    )
    assert [(s.core, s.start, s.end) for s in spans] == [
        ("a", d(2021), d(2023)),
        ("b", d(2023), None),
    ]


def test_complex_values_are_not_checkable():
    fact = Fact(
        "default:x", "default", "x", [Span("(p) => p.includes('x')", "", d(2021), None)], d(2021)
    )
    assert checkable(fact)


# ---- generation --------------------------------------------------------------------------
def _fact():
    spans = [
        Span(
            "3000", "`3000`", d(2021, 3), d(2022, 5, 12), [seg(d(2021, 3), d(2022, 5, 12), "3000")]
        ),
        Span("5173", "`5173`", d(2022, 5, 12), None, [seg(d(2022, 5, 12), None, "5173")]),
    ]
    return Fact("default:server.port", "default", "server.port", spans, d(2021, 10))


def test_phrase_dates_fall_inside_the_span_and_match_the_parser():
    span = _fact().spans[0]
    for phrase, as_of in phrase_options(span, NOW, R, P, random.Random(1)):
        assert span.start + timedelta(days=13) <= as_of < span.end
        q = f"What was the default value of `server.port` {phrase}?"
        assert parse_time(q, NOW, releases=R, prereleases=P).as_of == as_of, phrase


def test_generate_is_deterministic_and_typed():
    a = generate([_fact()], NOW, R, P, seed=3)
    b = generate([_fact()], NOW, R, P, seed=3)
    assert [q.to_json() for q in a] == [q.to_json() for q in b]
    types = {q.type for q in a}
    assert {"point_in_time", "current", "unanswerable", "change"} <= types
    current = next(q for q in a if q.type == "current")
    assert current.gold_tokens == ["5173"] and current.stale_tokens == ["3000"]
    unanswerable = next(q for q in a if q.type == "unanswerable")
    assert not unanswerable.answerable and datetime.fromisoformat(unanswerable.as_of) < d(2021, 8)


# ---- regressions found in the first review pass ------------------------------------------
def test_numbers_inside_identifiers_are_not_tokens():
    assert key_tokens("es2020") == ["es2020"]


def test_heading_badges_are_stripped_from_option_names():
    from app.evaluation.facts import _option_name

    name = _option_name("Dep Optimization Options > optimizeDeps.disabled <NonInheritBadge />")
    assert name == "optimizeDeps.disabled"


def test_node_versions_separated_by_a_period_are_kept():
    from app.evaluation.facts import _NODE

    text = "Vite requires [Node.js](https://nodejs.org/en/) version 18+. 20+. However, some"
    assert key_tokens(_NODE.search(text).group(1)) == ["18", "20"]


def test_tokens_in_the_gold_default_text_are_not_stale():
    from app.evaluation.questions import _stale

    old = Span("build.minify", "the same as `build.minify`", d(2023), d(2026), [])
    new = Span("lightningcss", "`'lightningcss'`, but `false` if `build.minify` is disabled",
               d(2026), None, [])  # fmt: skip
    fact = Fact("default:build.cssMinify", "default", "build.cssMinify", [old, new], d(2023))
    assert _stale(fact, new) == []
    assert _stale(fact, old) == ["lightningcss"]
