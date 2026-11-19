"""The web demo (web/) is served by the API at /demo; its precomputed examples are well formed."""

import json
from pathlib import Path

import httpx

from app.main import app

WEB = Path(__file__).resolve().parents[2] / "web"


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_demo_page_is_served():
    async with client() as c:
        page = await c.get("/demo/")
        script = await c.get("/demo/app.js")
        redirect = await c.get("/demo")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert '<h1 class="mast-name">TRACE</h1>' in page.text and "app.js" in page.text
    assert script.status_code == 200
    assert redirect.status_code in (307, 308) and redirect.headers["location"].endswith("/demo/")


async def test_api_routes_still_answer_json():
    async with client() as c:
        health = await c.get("/health")
        missing = await c.get("/no-such-route")
    assert health.json() == {"status": "ok"}
    assert missing.status_code == 404 and "error" in missing.json()


async def test_no_cors_headers_by_default():
    async with client() as c:
        r = await c.get("/health", headers={"Origin": "https://example.org"})
    assert "access-control-allow-origin" not in r.headers


def test_examples_are_complete():
    examples = json.loads((WEB / "examples.json").read_text(encoding="utf-8"))
    assert len(examples) >= 3
    for ex in examples:
        assert ex["question"]
        for kind in ("trace", "plain"):
            body = ex[kind]
            assert "answer" in body and "sources" in body and "cited_labels" in body
        assert ex["trace"]["time"]["as_of"]
        cited = {
            str(s["chunk_id"])
            for kind in ("trace", "plain")
            for s in ex[kind]["sources"]
            if s["label"] in ex[kind]["cited_labels"]
        }
        assert cited <= set(ex["lineages"]), "every cited source needs its history for offline use"
