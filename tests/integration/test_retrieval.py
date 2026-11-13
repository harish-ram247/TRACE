"""Time-filtered hybrid retrieval against a real PostgreSQL, using the offline hash embedder."""

import pytest

from app.ingest.service import ingest_repo
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import HashEmbedder
from app.retrieval.search import search, vector_candidates
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration

EMB = HashEmbedder()


@pytest.fixture
def corpus(pg, tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write(
        "server.md",
        "# Server Options\n\n## server.port\n\nThe dev server port defaults to 3000.\n\n"
        "## server.host\n\nThe dev server listens on localhost by default.\n",
    )
    b.write("css.md", "# CSS\n\n## CSS Modules\n\nFiles ending in .module.css are CSS modules.\n")
    b.commit("v1", day(2021, 1, 1))
    b.write(
        "server.md",
        "# Server Options\n\n## server.port\n\nThe dev server port defaults to 5173.\n\n"
        "## server.host\n\nThe dev server listens on localhost by default.\n",
    )
    b.commit("v2", day(2022, 7, 1))
    repo_id = str(b.path)
    ingest_repo(pg, b.path, repo_id)
    embed_missing(pg, EMB, repo_id)
    return repo_id


def test_backfill_embeds_every_chunk_once(pg, corpus):
    scoped = "FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.repo_url = %s"
    missing = pg.execute(f"SELECT count(*) {scoped} AND c.embedding IS NULL", (corpus,))
    assert missing.fetchone()[0] == 0
    assert embed_missing(pg, EMB, corpus) == 0  # idempotent
    models = pg.execute(f"SELECT DISTINCT c.embedding_model {scoped}", (corpus,)).fetchall()
    assert models == [(EMB.name,)]


def test_time_filter_returns_only_the_version_valid_then(pg, corpus):
    q = "What port does the dev server use by default?"
    old = search(pg, q, day(2021, 6, 1), embedder=EMB, repo_id=corpus)
    new = search(pg, q, day(2023, 1, 1), embedder=EMB, repo_id=corpus)
    assert "3000" in old[0].text and old[0].section_path == "Server Options > server.port"
    (new_port,) = [h for h in new if h.section_path.endswith("server.port")]
    assert "5173" in new_port.text
    assert all("5173" not in h.text for h in old)
    assert all("3000" not in h.text for h in new)
    assert all(h.valid_from <= day(2021, 6, 1) for h in old)


def test_without_time_filter_both_versions_compete(pg, corpus):
    hits = search(
        pg, "dev server port default", None, embedder=EMB, repo_id=corpus, time_filter=False
    )
    port_texts = [h.text for h in hits if h.section_path.endswith("server.port")]
    assert any("3000" in t for t in port_texts) and any("5173" in t for t in port_texts)


def test_nothing_is_valid_before_the_first_commit(pg, corpus):
    assert search(pg, "dev server port", day(2020, 1, 1), embedder=EMB, repo_id=corpus) == []


def test_single_branches_work_and_report_their_rank(pg, corpus):
    kw = search(
        pg, "module css", day(2023, 1, 1), embedder=EMB, repo_id=corpus, branches=("keyword",)
    )
    assert kw[0].section_path == "CSS > CSS Modules"
    assert kw[0].keyword_rank == 1 and kw[0].vector_rank is None
    vec = search(
        pg, "css modules", day(2023, 1, 1), embedder=EMB, repo_id=corpus, branches=("vector",)
    )
    assert vec[0].vector_rank == 1 and vec[0].keyword_rank is None


def test_vector_modes_agree_on_a_tiny_corpus(pg, corpus):
    qv = EMB.embed_query("dev server port")
    where, params = " AND c.valid @> %(as_of)s::timestamptz", {"as_of": day(2023, 1, 1)}
    exact = vector_candidates(pg, qv, where, params, 10, mode="exact")
    iterative = vector_candidates(pg, qv, where, params, 10, mode="iterative")
    assert iterative == exact
