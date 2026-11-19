"""TRACE demo: ask the Vite documentation a question as of any date.

Run:  streamlit run ui/app.py      (from the repo root, so .streamlit/config.toml applies;
                                    needs the API: uvicorn app.main:app)
Config: TRACE_API_URL (default http://127.0.0.1:8000; "localhost" costs ~2 s per call on Windows,
which tries IPv6 first while uvicorn listens on IPv4 only)

The UI only talks to the HTTP API, so it can run in its own container. Each "Ask" costs LLM calls,
so inputs live in a form (nothing is sent until the button is pressed) and responses are cached.
On first load the page shows one finished example (a cached answer) so the comparison is visible
before the visitor types. Styling lives in ui/style.css. Text from the LLM or the user is
HTML-escaped before it goes into custom HTML; the answer itself is rendered as Markdown without raw
HTML.
"""

from __future__ import annotations

import html
import os
import re
from datetime import UTC, date, datetime, time
from pathlib import Path

import httpx
import streamlit as st

API = os.environ.get("TRACE_API_URL", "http://127.0.0.1:8000").rstrip("/")
REPO_URL = "https://github.com/harish-ram247/TRACE"
FIRST_DATE, LAST_DATE = date(2021, 1, 1), date(2026, 11, 13)  # corpus history, pinned commit
EXAMPLES = [
    "",
    "What port does vite preview use by default?",
    "What is the default value of build.target?",
    "Which minifier does Vite use by default for production builds?",
    "Which Node.js version does Vite require?",
    "Which IP address does the dev server listen on by default?",
    "What was the default dev server port before Vite 3?",
]
VARIANTS = {
    "TRACE": "temporal",
    "TRACE + claim check": "temporal_verified",
}
# The finished example shown on first load (answers are cached by the API).
DEFAULT_EXAMPLE = (EXAMPLES[1], "temporal_verified", date(2022, 1, 1))
# claim label -> (css class, verdict word)
CLAIM_STYLE = {
    "supported_current": ("ok", "Supported"),
    "supported_outdated": ("bad", "Outdated source"),
    "unsupported": ("bad", "Unsupported"),
}
# verification action -> summary sentence
ACTION_TEXT = {
    "keep": "Every claim is supported by a source valid on that date.",
    "revised": "The answer was revised to drop what the sources did not support.",
    "dropped_claims": "Unsupported claims were removed from the answer.",
    "abstained": "No claim could be supported, so TRACE declined to answer.",
    "nothing_to_verify": "Nothing to verify.",
}
CITATION = re.compile(r"\[(S\d+)\]")

st.set_page_config(
    page_title="TRACE · time-aware answers from the Vite docs",
    page_icon=":material/history:",
    layout="wide",
)


class ApiFailure(Exception):
    """A non-200 answer. Raised inside the cached functions so errors are never cached:
    st.cache_data only stores return values, so the next try reaches the API again."""

    def __init__(self, status: int, body: dict):
        super().__init__(status)
        self.status, self.body = status, body


def _send(method: str, path: str, *, json: dict | None = None, timeout: float) -> dict:
    try:
        r = httpx.request(method, f"{API}{path}", json=json, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise ApiFailure(504, {"error": {"message": "no answer in time"}}) from exc
    except httpx.HTTPError as exc:
        raise ApiFailure(
            0, {"error": {"message": f"cannot reach the API at {API}: {exc}"}}
        ) from exc
    try:
        body = r.json()
    except ValueError:
        body = {"error": {"message": r.text[:200]}}
    if r.status_code != 200:
        raise ApiFailure(r.status_code, body)
    return body


@st.cache_data(ttl=3600, show_spinner=False)
def _ask_cached(question: str, variant: str, as_of: str | None) -> dict:
    body = {"question": question, "variant": variant}
    if as_of:
        body["as_of"] = as_of
    # Generous timeout: when the LLM provider is overloaded the API retries with backoff.
    return _send("POST", "/ask", json=body, timeout=300)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached(path: str) -> dict:
    return _send("GET", path, timeout=30)


def post_ask(question: str, variant: str, as_of: str | None) -> tuple[int, dict]:
    try:
        return 200, _ask_cached(question, variant, as_of)
    except ApiFailure as exc:
        return exc.status, exc.body


def get_json(path: str) -> tuple[int, dict]:
    try:
        return 200, _get_cached(path)
    except ApiFailure as exc:
        return exc.status, exc.body


def show_error(status: int, body: dict) -> None:
    err = body.get("error", {})
    msg = err.get("message", body)
    if status == 429:
        st.warning("Too many questions in a short time. Please wait a moment and try again.")
    elif status in (502, 504):
        st.warning(
            "The language model is busy or unavailable right now (it runs on a free tier). "
            "Please try again in a minute."
        )
    elif status == 503:
        st.error(f"The server is not fully configured: {msg}")
    else:
        st.error(f"Request failed ({status or 'no response'}): {msg}")
    if err.get("request_id"):
        st.caption(f"request id: {err['request_id']}")


# ---------------------------------------------------------------------------------------------
# Rendering helpers


def html_block(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def esc(value: object) -> str:
    return html.escape(str(value))


def fmt_day(value: str | None) -> str:
    return value[:10] if value else "now"


def to_date(value: str | None, default: date) -> date:
    return date.fromisoformat(value[:10]) if value else default


def timeline_pct(d: date) -> float:
    span = (LAST_DATE - FIRST_DATE).days
    return min(max((d - FIRST_DATE).days / span * 100, 0.0), 100.0)


def validity(s: dict, ref: date | None) -> tuple[str, str]:
    """(css class, word) for a source relative to the date asked."""
    if ref is None:
        return "na", "—"
    start = to_date(s["valid_from"], FIRST_DATE)
    if ref < start:
        return "bad", "Not yet written"
    if s["valid_until"] and ref >= to_date(s["valid_until"], LAST_DATE):
        return "bad", "Superseded"
    return "ok", "Valid"


def masthead() -> None:
    html_block(
        f"""
<header class="mast">
  <h1 class="mast-name">TRACE</h1>
  <div>
    <div class="mast-exp"><b>T</b>emporal <b>R</b>etrieval with <b>A</b>ttributed
      <b>C</b>laim <b>E</b>vidence</div>
    <p class="mast-desc">Ask the Vite documentation a question as of any date. TRACE answers only
      from the version of the docs that was valid then, cites it, and checks every claim.</p>
  </div>
  <a class="mast-link" href="{REPO_URL}" target="_blank" rel="noopener">Source on GitHub</a>
</header>
"""
    )


def strip_html(question: str, body: dict | None) -> str:
    """The yellow validity strip: what was asked, for which date, and the source's validity."""
    parts = []
    t = body.get("time") if body else None
    if t:
        parts.append(f'<span><span class="k">Asked for</span><b>{esc(t["as_of"][:10])}</b></span>')
    cited = [s for s in body["sources"] if s["label"] in set(body["cited_labels"])] if body else []
    if cited:
        s = cited[0]
        parts.append(
            f'<span><span class="k">Source valid</span><b>{esc(fmt_day(s["valid_from"]))} – '
            f"{esc(fmt_day(s['valid_until']))}</b></span>"
        )
    parts.append(
        f'<span><span class="k">Corpus</span>Vite docs, 2020-12 – {LAST_DATE.isoformat()}</span>'
    )
    return f'<div class="strip" role="status">{"".join(parts)}</div>'


def when_line(t: dict | None) -> str:
    if not t:
        return '<p class="when">No time handling: searches every version ever written.</p>'
    day = esc(t["as_of"][:10])
    if t["source"] == "explicit":
        why = "date set with the slider"
    elif t["assumed"]:
        why = "no date in the question, so today"
    else:
        why = f"read from “{esc(t['matched'])}”"
    return f'<p class="when">Answering as of <b>{day}</b>, {why}.</p>'


def sources_table(sources: list[dict], ref: date | None) -> str:
    head_ref = f"On {ref.isoformat()}" if ref else "Status"
    rows = []
    for s in sources:
        cls, word = validity(s, ref)
        rows.append(
            f'<tr><td class="id">{esc(s["label"])}</td>'
            f"<td>{esc(s['section_path'].split(' > ')[-1])}"
            f'<span class="file hide-sm">{esc(s["source_path"])}</span></td>'
            f'<td class="date">{esc(fmt_day(s["valid_from"]))}</td>'
            f'<td class="date">{esc(fmt_day(s["valid_until"]))}</td>'
            f'<td><span class="st {cls}">{word}</span></td></tr>'
        )
    return (
        '<div class="tt-scroll"><table class="tt src"><thead><tr><th></th><th>Section</th>'
        f"<th>Valid from</th><th>Until</th><th>{esc(head_ref)}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def source_timeline(sources: list[dict], ref: date | None) -> str:
    """One bar per cited source, drawn to time scale; the black tick is the date asked."""
    rows = []
    for s in sources:
        start = to_date(s["valid_from"], FIRST_DATE)
        end = to_date(s["valid_until"], LAST_DATE)
        left = timeline_pct(start)
        width = max(timeline_pct(end) - left, 0.6)
        cls = "bad" if validity(s, ref)[0] == "bad" else "ok"
        mark = f'<div class="tl-mark" style="left:{timeline_pct(ref):.2f}%"></div>' if ref else ""
        rows.append(
            f'<div class="tl-row"><span class="lbl">{esc(s["label"])}</span>'
            f'<div class="tl-track"><div class="tl-seg {cls}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%"></div>{mark}</div></div>'
        )
    years = "".join(
        f'<span style="left:{timeline_pct(date(y, 1, 1)):.2f}%">{y}</span>'
        for y in range(FIRST_DATE.year, LAST_DATE.year + 1)
    )
    key = (
        '<div class="tl-key"><span><i style="background:#003082"></i>valid on the date asked</span>'
        '<span><i style="background:#c8102e"></i>not valid on that date</span>'
        '<span><i style="background:#111;width:3px"></i>date asked</span></div>'
    )
    return (
        f'<div class="tl" aria-hidden="true">{"".join(rows)}<div class="tl-axis"><span></span>'
        f'<div class="years">{years}</div></div>{key}</div>'
    )


def claims_table(v: dict) -> str:
    rows = []
    for c in v["revised_claims"] or v["claims"]:
        cls, word = CLAIM_STYLE.get(c["label"], ("na", c["label"]))
        rows.append(
            f'<tr><td class="v"><span class="st {cls}">{word}</span></td>'
            f"<td>{esc(c['text'])}</td>"
            f'<td class="date">{c["entailment"]:.2f}</td></tr>'
        )
    summary = esc(ACTION_TEXT.get(v["action"], v["action"]))
    table = (
        '<div class="tt-scroll"><table class="tt claims"><thead><tr><th>Verdict</th><th>Claim</th>'
        f"<th>Entailment</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        if rows
        else ""
    )
    return f'<div class="tlabel">Claim check</div><p class="claim-sum">{summary}</p>{table}'


def answer_html(text: str) -> str:
    """The LLM's answer as safe HTML: escaped first, then `code`, **bold** and [S1] restored."""
    s = esc(text)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return CITATION.sub(r'<span class="cid">\1</span>', s)


def grid_row(name: str, role: str, status: int, body: dict, ref: date | None) -> str:
    """One system as one row of the timetable: answer, source validity, status, claims."""
    head = (
        f'<div class="g-sys"><span class="g-name">{name}</span>'
        f'<span class="g-role">{role}</span></div>'
    )
    if status != 200:
        msg = "The language model is busy; try again in a minute." if status in (502, 504) else (
            "No answer: the request failed."
        )  # fmt: skip
        return f'<div class="g-row">{head}<div class="g-ans g-muted">{esc(msg)}</div></div>'
    cited = [s for s in body["sources"] if s["label"] in set(body["cited_labels"])]
    stale = [s for s in cited if validity(s, ref)[0] == "bad"]
    if body["not_found"]:
        answer = '<span class="g-muted">Not found: the sources do not answer this.</span>'
    else:
        answer = answer_html(body["answer"])
    if stale:
        notes = "; ".join(
            f"{esc(s['label'])} was {validity(s, ref)[1].lower()} on {ref.isoformat()}"
            for s in stale
        )
        answer += (
            f'<sup class="g-x">†</sup><div class="g-note"><span class="g-x">†</span> {notes}.</div>'
        )
    lines = (
        "".join(
            f'<div class="g-src"><span class="cid">{esc(s["label"])}</span>'
            f'<span class="g-dates {validity(s, ref)[0]}">{esc(fmt_day(s["valid_from"]))} – '
            f"{esc(fmt_day(s['valid_until']))}</span></div>"
            for s in cited
        )
        or '<span class="g-muted">—</span>'
    )
    states = "".join(
        '<div class="g-src"><span class="st {}">{}</span></div>'.format(*validity(s, ref))
        for s in cited
    )
    v = body.get("verification")
    if v and v["claims"]:
        rows = v["revised_claims"] or v["claims"]
        ok = sum(c["label"] == "supported_current" for c in rows)
        claims = f"{ok} of {len(rows)} supported"
    else:
        claims = '<span class="g-muted">not checked</span>'
    return (
        f'<div class="g-row">{head}<div class="g-ans">{answer}</div>'
        f'<div class="g-cell" data-k="Cited source valid">{lines}</div>'
        f'<div class="g-cell" data-k="On the date asked">{states}</div>'
        f'<div class="g-cell" data-k="Claims">{claims}</div></div>'
    )


def summary_grid(rows: list[str], ref: date | None, extra_class: str) -> str:
    on = f"On {ref.isoformat()}" if ref else "Status"
    return (
        f'<div class="grid {extra_class}" role="table" aria-label="Answers compared">'
        '<div class="g-head" role="row"><span>System</span><span>Answer</span>'
        f"<span>Cited source valid</span><span>{esc(on)}</span><span>Claims</span></div>"
        f"{''.join(rows)}</div>"
    )


def show_answer(body: dict, kind: str, ref: date | None) -> None:
    """Detail for one system (the answer itself is in the summary grid above).
    kind: 'trace' or 'plain'. ref: the date the question is about."""
    t = body.get("time")
    if kind == "trace":
        name = "TRACE + claim check" if body.get("verification") else "TRACE"
        role = "time-aware"
    else:
        name, role = "Plain RAG", "baseline"

    with st.container(key=f"col-{kind}"):
        html_block(
            f'<div class="col-head"><span class="col-name">{name}</span>'
            f'<span class="col-role">{role}</span></div>{when_line(t)}'
        )
        cited = set(body["cited_labels"])
        sources = [s for s in body["sources"] if s["label"] in cited]
        if sources:
            html_block('<div class="tlabel">Cited sources</div>')
            html_block(sources_table(sources, ref))
            html_block(source_timeline(sources, ref))
            for s in sources:
                section = s["section_path"].split(" > ")[-1]
                with st.expander(f"{s['label']} · {section} · read this version"):
                    st.caption(f"{s['source_path']} · {s['section_path']}")
                    st.markdown(s["text"])
                    if st.button(
                        "Show every version of this section",
                        key=f"hist-{kind}-{s['chunk_id']}",
                        icon=":material/history:",
                    ):
                        st.session_state["history_chunk"] = s["chunk_id"]

        v = body.get("verification")
        if v:
            html_block(claims_table(v))


def show_history(chunk_id: int) -> None:
    status, chunk = get_json(f"/chunks/{chunk_id}")
    if status != 200:
        show_error(status, chunk)
        return
    status, lineage = get_json(f"/lineages/{chunk['lineage_id']}")
    if status != 200:
        show_error(status, lineage)
        return
    with st.container(key="history"):
        n = len(lineage["versions"])
        html_block(
            f'<div class="col-head"><span class="col-name">Every version of '
            f"“{esc(chunk['section_path'].split(' > ')[-1])}”</span>"
            f'<span class="col-role">{n} versions</span></div>'
            f'<p class="when">{esc(chunk["source_path"])} · {esc(chunk["section_path"])}</p>'
        )
        for v in lineage["versions"]:
            here = v["id"] == chunk_id
            label = f"{fmt_day(v['valid_from'])} – {fmt_day(v['valid_until'])}"
            if v["introduced_commit"]:
                label += f" · commit {v['introduced_commit'][:10]}"
            if here:
                label += " · the version cited"
            with st.expander(label, expanded=here):
                st.markdown(v["text"])


def how_it_works() -> None:
    steps = [
        (
            "Resolve the date",
            "From the slider, or from the question: “before Vite 3”, “in March 2022”.",
        ),
        (
            "Retrieve what was valid then",
            "Every section of the docs is versioned from git history "
            "with the dates it was valid; search only sees versions valid on that date.",
        ),  # fmt: skip
        (
            "Verify each claim",
            "An entailment model checks every claim in the answer against the "
            "cited source, and checks that the source was valid on that date.",
        ),  # fmt: skip
    ]
    rows = "".join(
        f"<tr><td>{i}</td><td>{esc(a)}</td><td>{esc(b)}</td></tr>"
        for i, (a, b) in enumerate(steps, 1)
    )
    html_block(
        '<section class="how"><div class="tlabel">How it works</div>'
        f'<div class="tt-scroll"><table class="tt"><tbody>{rows}</tbody></table></div></section>'
    )


# ---------------------------------------------------------------------------------------------
html_block(f"<style>{(Path(__file__).parent / 'style.css').read_text(encoding='utf-8')}</style>")
masthead()
strip_slot = st.empty()
grid_top = st.empty()  # phones: the comparison comes before the form

ex_q, ex_variant, ex_day = DEFAULT_EXAMPLE
with st.form("ask"):
    c_q, c_ex = st.columns([3, 2], gap="medium")
    with c_ex:
        example = st.selectbox("Examples", EXAMPLES, index=1)
    with c_q:
        question = st.text_input("Question", value=example or "", max_chars=500)
    c_date, c_sys, c_go = st.columns([5, 3, 2], gap="large", vertical_alignment="bottom")
    with c_date:
        use_slider = st.toggle(
            "Use the slider date",
            value=True,
            help="Turn off to read the date from the question, e.g. “before Vite 3”.",
        )
        day = st.slider("As of", FIRST_DATE, LAST_DATE, ex_day, format="YYYY-MM-DD")
    with c_sys:
        variant_name = st.radio("System", list(VARIANTS), index=1)
        compare = st.checkbox("Compare with plain RAG", value=True)
    with c_go:
        submitted = st.form_submit_button(
            "Ask", type="primary", icon=":material/search:", use_container_width=True
        )
grid_below = st.empty()  # wider screens: the comparison sits under the form

if submitted and len(question.strip()) >= 3:
    as_of = datetime.combine(day, time(23, 59, 59), tzinfo=UTC).isoformat() if use_slider else None
    st.session_state["last"] = (question.strip(), VARIANTS[variant_name], as_of, compare)
    st.session_state.pop("history_chunk", None)
elif submitted:
    st.warning("Please type a question (at least 3 characters).")

if "last" not in st.session_state:  # first visit: show the finished example
    ex_as_of = datetime.combine(ex_day, time(23, 59, 59), tzinfo=UTC).isoformat()
    st.session_state["last"] = (ex_q, ex_variant, ex_as_of, True)

q, variant, as_of, compare = st.session_state["last"]
with grid_below, st.spinner("Resolving the date, retrieving the docs valid then, answering…"):
    status, body = post_ask(q, variant, as_of)
    if compare:
        p_status, p_body = post_ask(q, "plain", None)
ref = to_date(body["time"]["as_of"], LAST_DATE) if status == 200 and body.get("time") else None
strip_slot.markdown(strip_html(q, body if status == 200 else None), unsafe_allow_html=True)

# One timetable: both systems as rows under one header (shown above the form on phones).
trace_name = "TRACE + claim check" if variant == "temporal_verified" else "TRACE"
rows = [grid_row(trace_name, "time-aware", status, body, ref)]
if compare:
    rows.append(grid_row("Plain RAG", "baseline", p_status, p_body, ref))
grid_top.markdown(summary_grid(rows, ref, "grid-m"), unsafe_allow_html=True)
grid_below.markdown(summary_grid(rows, ref, "grid-d"), unsafe_allow_html=True)

# Detail per system: sources, validity timeline, claim check, source text and history.
html_block('<div class="detail-gap" aria-hidden="true"></div>')
cols = st.columns(2, gap="large") if compare else [st.container()]
with cols[0]:
    if status == 200:
        show_answer(body, "trace", ref)
    else:
        show_error(status, body)
if compare:
    with cols[1]:
        if p_status == 200:
            show_answer(p_body, "plain", ref)
        else:
            show_error(p_status, p_body)

if chunk_id := st.session_state.get("history_chunk"):
    show_history(chunk_id)

how_it_works()
html_block(
    '<div class="foot">Corpus: Vite documentation (MIT License, © VoidZero Inc. and Vite '
    "contributors), git history up to 2026-11-13. Answers are generated by an LLM and may be "
    "wrong; check the cited sources.</div>"
)
