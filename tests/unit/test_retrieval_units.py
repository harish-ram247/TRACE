import numpy as np
import pytest

from app.retrieval.embeddings import HashEmbedder, passage_text
from app.retrieval.search import _filters, rrf


def test_rrf_rewards_items_ranked_high_in_both_lists():
    scores = rrf([[1, 2, 3], [3, 1, 4]], k=60)
    assert scores[1] > scores[3] > scores[2] > scores[4]
    assert scores[1] == pytest.approx(1 / 61 + 1 / 62)


def test_rrf_handles_empty_lists():
    assert rrf([[], []]) == {}
    assert rrf([[7], []]) == {7: pytest.approx(1 / 61)}


def test_hash_embedder_is_deterministic_normalised_and_word_sensitive():
    e = HashEmbedder()
    a, b, c = e.embed_passages(["dev server port", "dev server port", "css modules naming"])
    assert np.allclose(a, b)
    assert np.linalg.norm(a) == pytest.approx(1.0, abs=1e-5)
    q = e.embed_query("which port does the dev server use")
    assert float(q @ a) > float(q @ c)


def test_hash_embedder_never_returns_a_zero_vector():
    assert np.linalg.norm(HashEmbedder().embed_query("")) > 0


def test_passage_text_includes_heading_trail():
    assert passage_text("Server Options > server.port", "Default: 5173").startswith(
        "Server Options > server.port"
    )


def test_time_filter_requires_a_date():
    with pytest.raises(ValueError):
        _filters(None, None, time_filter=True)
    where, params = _filters(None, "r", time_filter=False)
    assert "valid" not in where and params == {"repo": "r"}
