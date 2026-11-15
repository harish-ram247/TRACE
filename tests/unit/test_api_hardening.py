import httpx
import pytest

from app.api.ratelimit import TokenBucket
from app.jobs.worker import JobError, resolve_repo
from app.main import app


def test_token_bucket_allows_a_burst_then_refills():
    t = {"now": 0.0}
    b = TokenBucket(per_minute=60, burst=2, clock=lambda: t["now"])  # 1 token per second
    assert b.take("ip") == 0 and b.take("ip") == 0
    wait = b.take("ip")
    assert 0.9 < wait <= 1.0
    t["now"] += 1.0
    assert b.take("ip") == 0
    assert b.take("other") == 0  # buckets are per client


def test_ingest_paths_must_stay_inside_the_root(tmp_path):
    root = tmp_path / "corpus"
    (root / "repo" / ".git").mkdir(parents=True)
    assert resolve_repo("repo", str(root)) == (root / "repo").resolve()
    with pytest.raises(JobError, match="inside"):
        resolve_repo("../../etc", str(root))
    with pytest.raises(JobError, match="inside"):
        resolve_repo(str(tmp_path), str(root))
    (root / "notgit").mkdir()
    with pytest.raises(JobError, match="not a git"):
        resolve_repo("notgit", str(root))


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_errors_share_one_shape_and_carry_a_request_id():
    async with await _client() as c:
        r = await c.get("/no-such-route")
        assert r.status_code == 404
        body = r.json()["error"]
        assert body["code"] == "not_found" and body["request_id"] == r.headers["x-request-id"]

        r = await c.post("/ask", json={"question": "x"}, headers={"X-Request-ID": "abc-123"})
        assert r.status_code == 422 and r.headers["x-request-id"] == "abc-123"
        problems = r.json()["error"]["message"]
        assert problems[0]["field"] == "question"


async def test_unsafe_request_ids_are_replaced():
    async with await _client() as c:
        r = await c.get("/health", headers={"X-Request-ID": "bad id with spaces\n"})
        assert r.headers["x-request-id"] != "bad id with spaces\n"


async def test_admin_endpoints_are_closed_without_a_configured_token():
    async with await _client() as c:
        r = await c.post("/ingest", json={"repo_path": "x", "repo_id": "y"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
