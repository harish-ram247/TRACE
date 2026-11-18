"""TRACE demo: ask the Vite documentation a question as of any date.

Run:  streamlit run ui/app.py      (from the repo root, so .streamlit/config.toml applies;
                                    needs the API: uvicorn app.main:app)
Config: TRACE_API_URL (default http://127.0.0.1:8000; "localhost" costs ~2 s per call on Windows,
which tries IPv6 first while uvicorn listens on IPv4 only)

The UI only talks to the HTTP API, so it can run in its own container. Each "Ask" costs LLM calls,
so inputs live in a form (nothing is sent until the button is pressed) and responses are cached.
Styling lives in ui/style.css. Text that comes from the LLM or the user is HTML-escaped before it is
put into custom HTML; the answer itself is rendered as Markdown without raw HTML.
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
    "TRACE (time-aware)": "temporal",
    "TRACE + claim verification": "temporal_verified",
}
# claim label -> (css class, icon, text)
CLAIM_STYLE = {
    "supported_current": ("ok", "✓", "supported by a source valid on that date"),
    "supported_outdated": ("warn", "!", "supported only by an outdated source"),
    "unsupported": ("bad", "✕", "not supported by the cited sources"),
}
# verification action -> (css class, text)
ACTION_STYLE = {
    "keep": ("ok", "all claims supported"),
    "revised": ("warn", "answer revised"),
    "dropped_claims": ("warn", "unsupported claims removed"),
    "abstained": ("bad", "abstained"),
    "nothing_to_verify": ("neutral", "nothing to verify"),
}
CITATION = re.compile(r"\[(S\d+)\]")

st.set_page_config(page_title="TRACE: time-aware docs QA", page_icon="⏳", layout="wide")


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


def fmt_day(value: str | None) -> str:
    return value[:10] if value else "now"


def to_date(value: str | None, default: date) -> date:
    return date.fromisoformat(value[:10]) if value else default


def timeline_pct(d: date) -> float:
    span = (LAST_DATE - FIRST_DATE).days
    return min(max((d - FIRST_DATE).days / span * 100, 0.0), 100.0)


def cite_badges(answer: str) -> str:
    """[S1] -> a small Streamlit badge (Markdown directive, no raw HTML)."""
    return CITATION.sub(r":orange-badge[\1]", answer)


def hero() -> None:
    html_block(
        """
<div class="hero">
  <div class="hero-badge"><span class="dot"></span>
    Time-aware RAG · Vite docs, every version 2021 → 2026</div>
  <div class="hero-title"><span class="glass">⏳</span><span class="word">TRACE</span></div>
  <div class="acronym"><b>T</b>emporal <b>R</b>etrieval with <b>A</b>ttributed
    <b>C</b>laim <b>E</b>vidence</div>
  <p class="tagline">Ask the documentation as it was on any date: every answer is cited from,
  and checked against, the version that was true then.</p>
</div>
<div class="steps">
  <div class="step"><div class="n">1</div><div><div class="t">Resolve the date</div>
    <div class="d">"before Vite 3", "in March 2022", or the slider</div></div></div>
  <div class="step"><div class="n">2</div><div><div class="t">Retrieve what was valid then</div>
    <div class="d">every doc section is versioned with a validity interval</div></div></div>
  <div class="step"><div class="n">3</div><div><div class="t">Verify each claim</div>
    <div class="d">an entailment model checks claims against the cited sources</div></div></div>
</div>
"""
    )


def when_chip(t: dict | None) -> str:
    if not t:
        return '<div class="when">🗂️ No time handling: searches every version ever written</div>'
    day = html.escape(t["as_of"][:10])
    if t["source"] == "explicit":
        why = "date picked on the slider"
    elif t["assumed"]:
        why = "no date in the question, so today"
    else:
        why = f"from “{html.escape(t['matched'])}” ({html.escape(t['intent'])})"
    return f'<div class="when">📅 Answering as of <b>{day}</b> · {why}</div>'


def source_timeline(sources: list[dict], ref: date | None) -> str:
    """One bar per cited source showing when it was valid; the amber line is the date asked."""
    rows = []
    for s in sources:
        start = to_date(s["valid_from"], FIRST_DATE)
        end = to_date(s["valid_until"], LAST_DATE)
        left = timeline_pct(start)
        width = max(timeline_pct(end) - left, 0.8)
        ok = ref is None or start <= ref < end or (s["valid_until"] is None and start <= ref)
        mark = f'<div class="tl-mark" style="left:{timeline_pct(ref):.2f}%"></div>' if ref else ""
        rows.append(
            f'<div class="tl-row"><span class="lbl">{html.escape(s["label"])}</span>'
            f'<div class="tl-track"><div class="tl-seg {"ok" if ok else "bad"}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%"></div>{mark}</div></div>'
        )
    years = "".join(
        f'<span style="left:{timeline_pct(date(y, 1, 1)):.2f}%">{y}</span>'
        for y in range(FIRST_DATE.year, LAST_DATE.year + 1)
    )
    legend = (
        '<div class="tl-legend">'
        '<span><i style="background:#34d3b5"></i>valid on the date asked</span>'
        '<span><i style="background:#f47a8a"></i>not valid on that date</span>'
        '<span><i style="background:#f2b84b;width:3px"></i>date asked</span></div>'
    )
    return (
        f'<div class="tl">{"".join(rows)}<div class="tl-axis"><span></span>'
        f'<div class="years">{years}</div></div>{legend}</div>'
    )


def claims_block(v: dict) -> str:
    cls, text = ACTION_STYLE.get(v["action"], ("neutral", v["action"]))
    rows = []
    for c in v["revised_claims"] or v["claims"]:
        ccls, icon, meaning = CLAIM_STYLE.get(c["label"], ("neutral", "•", c["label"]))
        rows.append(
            f'<div class="claim {ccls}"><span class="ic">{icon}</span><div>'
            f'<div class="tx">{html.escape(c["text"])}</div>'
            f'<div class="meta">{meaning} · entailment {c["entailment"]:.2f}</div></div></div>'
        )
    head = (
        f'<div class="section-label claims-head">Claim check '
        f'<span class="pill {cls}">{html.escape(text)}</span></div>'
    )
    return head + "".join(rows)


def show_answer(body: dict, kind: str, ref: date | None) -> None:
    """kind: 'trace' or 'plain'. ref: the date the question is about (marks the timeline)."""
    t = body.get("time")
    if kind == "trace":
        title, pill = (
            ("TRACE + claim verification" if body.get("verification") else "TRACE"),
            ('<span class="pill trace">time-aware</span>'),
        )
    else:
        title, pill = "Plain RAG", '<span class="pill plain">baseline</span>'

    with st.container(border=True, key=f"card-{kind}"):
        html_block(f'<div class="card-head"><span class="title">{title}</span>{pill}</div>')
        html_block(when_chip(t))

        if body["not_found"]:
            st.info(
                "NOT_FOUND: the documentation valid on that date does not answer this."
                if t
                else "NOT_FOUND: the retrieved passages do not answer this."
            )
        else:
            st.markdown(cite_badges(body["answer"]))

        cited = set(body["cited_labels"])
        sources = [s for s in body["sources"] if s["label"] in cited]
        if sources:
            html_block('<div class="section-label">When each cited source was valid</div>')
            html_block(source_timeline(sources, ref))
            html_block('<div class="section-label">Cited sources</div>')
        for s in sources:
            label = (f"{s['label']} · {s['section_path']}  ·  "
                     f"{fmt_day(s['valid_from'])} → {fmt_day(s['valid_until'])}")  # fmt: skip
            with st.expander(label):
                st.caption(s["source_path"])
                st.markdown(s["text"])
                if st.button(
                    "Show this section's full history",
                    key=f"hist-{kind}-{s['chunk_id']}",
                    icon=":material/history:",
                ):
                    st.session_state["history_chunk"] = s["chunk_id"]

        v = body.get("verification")
        if v:
            html_block(claims_block(v))


def show_history(chunk_id: int) -> None:
    status, chunk = get_json(f"/chunks/{chunk_id}")
    if status != 200:
        show_error(status, chunk)
        return
    status, lineage = get_json(f"/lineages/{chunk['lineage_id']}")
    if status != 200:
        show_error(status, lineage)
        return
    with st.container(border=True, key="card-history"):
        html_block(
            f'<div class="card-head"><span class="title">History of '
            f"“{html.escape(chunk['section_path'])}”</span>"
            f'<span class="pill neutral">{len(lineage["versions"])} versions</span></div>'
            f'<div class="when">📄 {html.escape(chunk["source_path"])}</div>'
        )
        for v in lineage["versions"]:
            here = v["id"] == chunk_id
            label = f"{fmt_day(v['valid_from'])} → {fmt_day(v['valid_until'])}"
            if here:
                label += "  ·  the version that was cited"
            with st.expander(label, expanded=here):
                st.markdown(v["text"])
                if v["introduced_commit"]:
                    st.caption(f"introduced in commit {v['introduced_commit'][:10]}")


# ---------------------------------------------------------------------------------------------
html_block(f"<style>{(Path(__file__).parent / 'style.css').read_text(encoding='utf-8')}</style>")
hero()

with st.form("ask"):
    example = st.selectbox("Pick an example, or type your own below", EXAMPLES, index=1)
    question = st.text_input("Question", value=example, max_chars=500)
    c1, c2 = st.columns([2, 1], gap="large")
    with c1:
        use_slider = st.toggle(
            "Pick the date with the slider (otherwise: the date in the question)", value=True
        )
        day = st.slider("As of", FIRST_DATE, LAST_DATE, date(2022, 1, 1), format="YYYY-MM-DD")
    with c2:
        variant_name = st.radio("System", list(VARIANTS))
        compare = st.checkbox("Compare with plain RAG", value=True)
    submitted = st.form_submit_button("Ask", type="primary", icon=":material/search:")

if submitted and len(question.strip()) >= 3:
    as_of = datetime.combine(day, time(23, 59, 59), tzinfo=UTC).isoformat() if use_slider else None
    st.session_state["last"] = (question.strip(), VARIANTS[variant_name], as_of, compare)
    st.session_state.pop("history_chunk", None)
elif submitted:
    st.warning("Please type a question (at least 3 characters).")

if "last" in st.session_state:
    q, variant, as_of, compare = st.session_state["last"]
    cols = st.columns(2, gap="medium") if compare else [st.container()]
    with st.spinner("Resolving the date, retrieving the docs valid then, answering…"):
        status, body = post_ask(q, variant, as_of)
    ref = to_date(body["time"]["as_of"], LAST_DATE) if status == 200 and body.get("time") else None
    with cols[0]:
        if status == 200:
            show_answer(body, "trace", ref)
        else:
            show_error(status, body)
    if compare:
        with st.spinner("Asking plain RAG…"):
            p_status, p_body = post_ask(q, "plain", None)
        with cols[1]:
            if p_status == 200:
                show_answer(p_body, "plain", ref)
            else:
                show_error(p_status, p_body)

if chunk_id := st.session_state.get("history_chunk"):
    show_history(chunk_id)

html_block(
    '<div class="foot">Corpus: Vite documentation (MIT License, © VoidZero Inc. and Vite '
    "contributors), git history up to 2026-11-13. Answers are generated by an LLM and may be "
    f'wrong; check the cited sources. · <a href="{REPO_URL}" target="_blank">Source on GitHub</a>'
    "</div>"
)
