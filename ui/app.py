"""TRACE demo: ask the Vite documentation a question as of any date.

Run:  streamlit run ui/app.py      (needs the API: uvicorn app.main:app)
Config: TRACE_API_URL (default http://localhost:8000)

The UI only talks to the HTTP API, so it can run in its own container. Each "Ask" costs LLM calls,
so inputs live in a form (nothing is sent until the button is pressed) and responses are cached.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time

import httpx
import streamlit as st

API = os.environ.get("TRACE_API_URL", "http://localhost:8000").rstrip("/")
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
LABEL_ICON = {"supported_current": "✅", "supported_outdated": "🕰️", "unsupported": "❌"}

st.set_page_config(page_title="TRACE: time-aware docs QA", page_icon="⏳", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def post_ask(question: str, variant: str, as_of: str | None) -> tuple[int, dict]:
    body = {"question": question, "variant": variant}
    if as_of:
        body["as_of"] = as_of
    try:
        r = httpx.post(f"{API}/ask", json=body, timeout=120)
        return r.status_code, r.json()
    except httpx.HTTPError as exc:
        return 0, {"error": {"message": f"cannot reach the API at {API}: {exc}"}}


@st.cache_data(ttl=3600, show_spinner=False)
def get_json(path: str) -> tuple[int, dict]:
    try:
        r = httpx.get(f"{API}{path}", timeout=30)
        return r.status_code, r.json()
    except httpx.HTTPError as exc:
        return 0, {"error": {"message": str(exc)}}


def show_error(status: int, body: dict) -> None:
    err = body.get("error", {})
    msg = err.get("message", body)
    if status == 429:
        st.warning("Too many questions in a short time. Please wait a moment and try again.")
    elif status == 503:
        st.error(f"The server is not fully configured: {msg}")
    else:
        st.error(f"Request failed ({status or 'no response'}): {msg}")
    if err.get("request_id"):
        st.caption(f"request id: {err['request_id']}")


def fmt_day(value: str | None) -> str:
    return value[:10] if value else "now"


def show_answer(body: dict, heading: str) -> None:
    st.subheader(heading)
    t = body.get("time")
    if t:
        when = t["as_of"][:10]
        if t["source"] == "explicit":
            st.caption(f"📅 Answering as of **{when}** (date picked on the slider)")
        elif t["assumed"]:
            st.caption(f"📅 No date in the question, so answering as of **{when}** (today)")
        else:
            st.caption(f'📅 "{t["matched"]}" → answering as of **{when}** ({t["intent"]})')
    else:
        st.caption("📅 No time handling: searches every version ever written")

    if body["not_found"]:
        st.info("NOT_FOUND: the documentation valid on that date does not answer this.")
    else:
        st.markdown(body["answer"])

    cited = set(body["cited_labels"])
    sources = [s for s in body["sources"] if s["label"] in cited]
    if sources:
        st.markdown("**Cited sources**")
    for s in sources:
        title = (f"[{s['label']}] {s['section_path']}  ·  valid {fmt_day(s['valid_from'])} → "
                 f"{fmt_day(s['valid_until'])}")  # fmt: skip
        with st.expander(title):
            st.caption(s["source_path"])
            st.markdown(s["text"])
            if st.button("Show this section's full history", key=f"hist-{heading}-{s['chunk_id']}"):
                st.session_state["history_chunk"] = s["chunk_id"]

    v = body.get("verification")
    if v:
        st.markdown(f"**Claim check:** `{v['action']}`")
        rows = v["revised_claims"] or v["claims"]
        for c in rows:
            icon = LABEL_ICON.get(c["label"], "•")
            detail = f"{c['label']}, entailment {c['entailment']:.2f}"
            st.markdown(f"{icon} {c['text']}  \n<small>{detail}</small>", unsafe_allow_html=True)


def show_history(chunk_id: int) -> None:
    status, chunk = get_json(f"/chunks/{chunk_id}")
    if status != 200:
        show_error(status, chunk)
        return
    status, lineage = get_json(f"/lineages/{chunk['lineage_id']}")
    if status != 200:
        show_error(status, lineage)
        return
    st.subheader(f"History of “{chunk['section_path']}”")
    st.caption(f"{len(lineage['versions'])} versions in {chunk['source_path']}")
    for v in lineage["versions"]:
        marker = "👉 " if v["id"] == chunk_id else ""
        label = f"{marker}{fmt_day(v['valid_from'])} → {fmt_day(v['valid_until'])}"
        with st.expander(label, expanded=v["id"] == chunk_id):
            st.markdown(v["text"])
            if v["introduced_commit"]:
                st.caption(f"introduced in commit {v['introduced_commit'][:10]}")


# ---------------------------------------------------------------------------------------------
st.title("⏳ TRACE")
st.markdown(
    "Ask the **Vite documentation** a question **as of any date**. TRACE retrieves only the "
    "version of the docs that was current then, and cites it. Compare it with plain RAG, which "
    "searches every version ever written."
)

with st.form("ask"):
    example = st.selectbox("Pick an example, or type your own below", EXAMPLES, index=1)
    question = st.text_input("Question", value=example, max_chars=500)
    c1, c2 = st.columns([2, 1])
    with c1:
        use_slider = st.toggle(
            "Pick the date with the slider (otherwise: the date in the question)", value=True
        )
        day = st.slider("As of", FIRST_DATE, LAST_DATE, date(2022, 1, 1), format="YYYY-MM-DD")
    with c2:
        variant_name = st.radio("System", list(VARIANTS))
        compare = st.checkbox("Compare with plain RAG", value=True)
    submitted = st.form_submit_button("Ask", type="primary")

if submitted and len(question.strip()) >= 3:
    as_of = datetime.combine(day, time(23, 59, 59), tzinfo=UTC).isoformat() if use_slider else None
    st.session_state["last"] = (question.strip(), VARIANTS[variant_name], as_of, compare)
    st.session_state.pop("history_chunk", None)
elif submitted:
    st.warning("Please type a question (at least 3 characters).")

if "last" in st.session_state:
    q, variant, as_of, compare = st.session_state["last"]
    cols = st.columns(2) if compare else [st.container()]
    with st.spinner("Asking…"):
        status, body = post_ask(q, variant, as_of)
    with cols[0]:
        if status == 200:
            show_answer(body, [k for k, v in VARIANTS.items() if v == variant][0])
        else:
            show_error(status, body)
    if compare:
        with st.spinner("Asking plain RAG…"):
            p_status, p_body = post_ask(q, "plain", None)
        with cols[1]:
            if p_status == 200:
                show_answer(p_body, "Plain RAG (no time awareness)")
            else:
                show_error(p_status, p_body)

if chunk_id := st.session_state.get("history_chunk"):
    st.divider()
    show_history(chunk_id)

st.divider()
st.caption(
    "Corpus: Vite documentation (MIT License, © VoidZero Inc. and Vite contributors), git history "
    "up to 2026-11-13. Answers are generated by an LLM and may be wrong; check the cited sources."
)
