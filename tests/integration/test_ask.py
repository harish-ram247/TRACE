"""Ask pipeline and POST /ask end to end, with the hash embedder and a fake LLM."""

import re

import httpx
import pytest

from app.api.ask import embedder_dep, llm_dep
from app.core.config import get_settings
from app.core.llm import FakeLLM
from app.core.pg import get_conn
from app.ingest.service import ingest_repo
from app.main import app
from app.pipeline import ask
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import HashEmbedder
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration

EMB = HashEmbedder()
# Attribute values can contain ">" (section paths like "A > B"), so match up to ">" + newline.
_SOURCE = re.compile(r'<source label="(S\d+)".*?>\n(.*?)\n</source>', re.DOTALL)


def port_reader(messages):
    """Fake model: reports the first port number it finds in the sources, citing that source."""
    for label, text in _SOURCE.findall(messages[-1]["content"]):
        if m := re.search(r"\b(3000|5173)\b", text):
            return f"The default port is {m.group(1)} [{label}]."
    return "NOT_FOUND"


@pytest.fixture
def corpus(pg, tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write(
        "server.md", "# Server Options\n\n## server.port\n\nThe dev server port defaults to 3000.\n"
    )
    b.commit("v1", day(2021, 1, 1))
    b.write(
        "server.md", "# Server Options\n\n## server.port\n\nThe dev server port defaults to 5173.\n"
    )
    b.commit("v2", day(2022, 7, 1))
    repo_id = str(b.path)
    ingest_repo(pg, b.path, repo_id)
    embed_missing(pg, EMB, repo_id)
    return repo_id


def run(pg, corpus, question, **kw):
    llm = FakeLLM(port_reader)
    return ask(pg, question, embedder=EMB, llm=llm, repo_id=corpus, **kw), llm


def test_question_date_selects_the_right_version(pg, corpus):
    result, llm = run(pg, corpus, "What was the dev server port in June 2021?")
    assert result.time.intent == "point_in_time"
    assert "3000" in result.answer.text and result.answer.citations
    assert "2021-06-30" in llm.calls[0]["messages"][0]["content"]


def test_current_question_uses_latest_version(pg, corpus):
    result, _ = run(pg, corpus, "What is the dev server port now?")
    assert result.time.intent == "current"
    assert "5173" in result.answer.text


def test_explicit_as_of_overrides_the_question(pg, corpus):
    result, _ = run(pg, corpus, "What is the dev server port now?", as_of=day(2021, 3, 1))
    assert result.time.source == "explicit" and "3000" in result.answer.text


def test_plain_baseline_sees_both_versions_and_no_dates(pg, corpus):
    result, llm = run(pg, corpus, "What was the dev server port in June 2021?", variant="plain")
    assert result.time is None
    texts = " ".join(h.text for h in result.hits)
    assert "3000" in texts and "5173" in texts
    assert "valid_from" not in llm.calls[0]["messages"][1]["content"]


def test_nothing_valid_yet_answers_not_found_without_llm(pg, corpus):
    result, llm = run(pg, corpus, "What was the dev server port in 2019?")
    assert result.answer.not_found and llm.calls == []


@pytest.fixture
def client(pg, corpus, monkeypatch):
    monkeypatch.setattr(get_settings(), "corpus_repo_id", corpus)
    app.dependency_overrides[get_conn] = lambda: pg
    app.dependency_overrides[embedder_dep] = lambda: EMB
    app.dependency_overrides[llm_dep] = lambda: FakeLLM(port_reader)
    yield httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


async def test_ask_endpoint_returns_answer_time_and_sources(client):
    async with client as c:
        r = await c.post("/ask", json={"question": "What was the dev server port in June 2021?"})
    assert r.status_code == 200
    body = r.json()
    assert "3000" in body["answer"] and body["cited_labels"] == ["S1"]
    assert body["time"]["intent"] == "point_in_time"
    assert body["sources"][0]["section_path"] == "Server Options > server.port"
    assert body["prompt_version"] == "answer-v3"


async def test_ask_endpoint_validates_input(client):
    async with client as c:
        r = await c.post("/ask", json={"question": "", "top_k": 50})
    assert r.status_code == 422
