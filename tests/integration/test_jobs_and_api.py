"""Job queue, worker and the new endpoints against a real PostgreSQL."""

import json
import re
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr

from app.api import ratelimit
from app.api.ask import embedder_dep, llm_dep, nli_dep
from app.api.ratelimit import TokenBucket
from app.core.config import get_settings
from app.core.llm import FakeLLM
from app.core.pg import get_conn
from app.ingest.service import ingest_repo
from app.jobs import queue, worker
from app.main import app
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import HashEmbedder
from app.verification.nli import KeywordNLI
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration
EMB = HashEmbedder()


# ---- queue -------------------------------------------------------------------------------
def test_claim_complete_and_skip_locked(pg):
    a = queue.enqueue(pg, "ingest", {"n": 1})
    b = queue.enqueue(pg, "ingest", {"n": 2})
    first = queue.claim(pg)
    second = queue.claim(pg)
    assert {first.id, second.id} == {a, b} and first.id != second.id
    assert first.attempts == 1 and first.payload == {"n": 1}
    queue.complete(pg, first.id, {"ok": True})
    assert queue.get(pg, first.id)["status"] == "done"
    third = queue.claim(pg)  # a and b are taken: never handed out twice
    assert third is None or third.id not in (a, b)


def test_failures_retry_with_backoff_then_give_up(pg):
    jid = queue.enqueue(pg, "ingest", {}, max_attempts=2)
    job = queue.claim(pg)
    assert queue.fail(pg, job, "boom") == "queued"
    row = pg.execute(
        "SELECT status, run_after > now(), error FROM jobs WHERE id = %s", (jid,)
    ).fetchone()
    assert row[0] == "queued" and row[1] is True and row[2] == "boom"
    pg.execute("UPDATE jobs SET run_after = now() WHERE id = %s", (jid,))
    job = queue.claim(pg)
    assert job.attempts == 2
    assert queue.fail(pg, job, "boom again") == "failed"
    assert queue.get(pg, jid)["status"] == "failed"


def test_stale_running_jobs_are_requeued(pg):
    jid = queue.enqueue(pg, "ingest", {})
    queue.claim(pg)
    pg.execute("UPDATE jobs SET locked_at = now() - interval '2 hours' WHERE id = %s", (jid,))
    assert queue.requeue_stale(pg, timedelta(hours=1)) >= 1
    assert queue.get(pg, jid)["status"] == "queued"


# ---- worker ------------------------------------------------------------------------------
@pytest.fixture
def corpus_root(tmp_path, monkeypatch):
    root = tmp_path / "corpus"
    b = RepoBuilder(root / "docs-repo")
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `5000`\n\nPreview port.\n")
    b.commit("v1", day(2021, 11, 6))
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `4173`\n\nPreview port.\n")
    b.commit("v2", day(2022, 1, 16))
    monkeypatch.setattr(get_settings(), "ingest_root", str(root))
    return root, b


def test_worker_runs_an_ingest_job(pg, corpus_root):
    root, b = corpus_root
    repo_id = f"test://{b.path.name}-{id(b)}"
    jid = queue.enqueue(pg, "ingest", {"repo_path": "docs-repo", "repo_id": repo_id})
    while (done := worker.run_once(pg, EMB)) is not None and done != jid:
        pass
    job = queue.get(pg, jid)
    assert job["status"] == "done", job["error"]
    assert job["result"]["chunks_added"] == 2 and job["result"]["embedded"] == 2


def test_bad_paths_fail_immediately_without_retries(pg, corpus_root):
    jid = queue.enqueue(pg, "ingest", {"repo_path": "../..", "repo_id": "x"}, max_attempts=3)
    while (done := worker.run_once(pg, EMB)) is not None and done != jid:
        pass
    job = queue.get(pg, jid)
    assert job["status"] == "failed" and job["attempts"] == 1 and "inside" in job["error"]


# ---- endpoints ---------------------------------------------------------------------------
_SOURCE = re.compile(r'<source label="(S\d+)".*?>\n(.*?)\n</source>', re.DOTALL)


def responder(messages):
    if "split an answer" in messages[0]["content"]:
        answer = messages[-1]["content"]
        found = re.findall(r"(\d{4}) \[(S\d+)\]", answer)
        claims = [
            {"text": f"The default of `preview.port` is `{n}`.", "sources": [s]} for n, s in found
        ]
        return json.dumps({"claims": claims})
    for label, text in _SOURCE.findall(messages[1]["content"]):
        if m := re.search(r"\b(5000|4173)\b", text):
            return f"The default port is {m.group(1)} [{label}]."
    return "NOT_FOUND"


@pytest.fixture
def api(pg, corpus_root, monkeypatch):
    _, b = corpus_root
    repo_id = f"api://{id(b)}"
    ingest_repo(pg, b.path, repo_id)
    embed_missing(pg, EMB, repo_id)
    monkeypatch.setattr(get_settings(), "corpus_repo_id", repo_id)
    monkeypatch.setattr(get_settings(), "admin_token", SecretStr("s3cret"))
    monkeypatch.setattr(ratelimit, "_bucket", TokenBucket(per_minute=1000))
    app.dependency_overrides[get_conn] = lambda: pg
    app.dependency_overrides[embedder_dep] = lambda: EMB
    app.dependency_overrides[llm_dep] = lambda: FakeLLM(responder)
    app.dependency_overrides[nli_dep] = lambda: lambda: KeywordNLI()
    yield httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), repo_id
    app.dependency_overrides.clear()


async def test_chunk_and_lineage_history(api, pg):
    client, repo_id = api
    lineage, first = pg.execute(
        "SELECT c.lineage_id, min(c.id) FROM chunks c JOIN documents d ON d.id = c.document_id "
        "WHERE d.repo_url = %s GROUP BY 1",
        (repo_id,),
    ).fetchone()
    async with client as c:
        chunk = (await c.get(f"/chunks/{first}")).json()
        history = (await c.get(f"/lineages/{lineage}")).json()
        missing = await c.get("/chunks/999999999")
    assert "5000" in chunk["text"] and chunk["valid_until"] is not None
    assert [("5000" in v["text"], "4173" in v["text"]) for v in history["versions"]] == [
        (True, False),
        (False, True),
    ]
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


async def test_ingest_endpoint_requires_the_admin_token_and_queues_a_job(api, pg):
    client, _ = api
    body = {"repo_path": "docs-repo", "repo_id": "test://queued"}
    async with client as c:
        assert (await c.post("/ingest", json=body)).status_code == 401
        assert (
            await c.post("/ingest", json=body, headers={"X-Admin-Token": "nope"})
        ).status_code == 401
        ok = await c.post("/ingest", json=body, headers={"X-Admin-Token": "s3cret"})
        assert ok.status_code == 202
        job = await c.get(f"/jobs/{ok.json()['job_id']}", headers={"X-Admin-Token": "s3cret"})
        bad = await c.post("/ingest", json={**body, "until": "HEAD; rm -rf /"},
                           headers={"X-Admin-Token": "s3cret"})  # fmt: skip
    assert job.json()["status"] == "queued" and job.json()["type"] == "ingest"
    assert bad.status_code == 422


async def test_ask_verified_variant_returns_claim_verdicts(api):
    client, _ = api
    async with client as c:
        r = await c.post("/ask", json={
            "question": "What was the default of preview.port in December 2021?",
            "variant": "temporal_verified",
        })  # fmt: skip
    body = r.json()
    assert r.status_code == 200 and "5000" in body["answer"]
    assert body["verification"]["action"] == "keep"
    assert body["verification"]["claims"][0]["label"] == "supported_current"


async def test_ask_is_rate_limited(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(ratelimit, "_bucket", TokenBucket(per_minute=1, burst=1))
    q = {"question": "What is the default of preview.port now?"}
    async with client as c:
        first = await c.post("/ask", json=q)
        second = await c.post("/ask", json=q)
    assert first.status_code == 200
    assert second.status_code == 429 and int(second.headers["retry-after"]) >= 1
    assert second.json()["error"]["code"] == "rate_limited"
