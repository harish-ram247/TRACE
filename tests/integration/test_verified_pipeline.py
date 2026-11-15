"""All four variants end to end, with the hash embedder, a fake LLM and the keyword NLI."""

import json
import re

import pytest

from app.core.llm import FakeLLM
from app.evaluation.harness import RunConfig, run
from app.evaluation.metrics import score_run
from app.ingest.service import ingest_repo
from app.pipeline import ask
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import HashEmbedder
from app.verification.nli import KeywordNLI
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration
EMB, NLI = HashEmbedder(), KeywordNLI()
_SOURCE = re.compile(r'<source label="(S\d+)".*?>\n(.*?)\n</source>', re.DOTALL)


def responder(messages):
    system = messages[0]["content"]
    if "split an answer" in system:  # claim extraction: one claim per cited number
        answer = messages[-1]["content"]
        claims = [
            {"text": f"The default of `preview.port` is `{n}`.", "sources": [lab]}
            for n, lab in re.findall(r"(\d{4}) \[(S\d+)\]", answer)
        ]
        return json.dumps({"claims": claims})
    for label, text in _SOURCE.findall(messages[1]["content"]):
        if m := re.search(r"\b(5000|4173)\b", text):
            return f"The default port is {m.group(1)} [{label}]."
    return "NOT_FOUND"


@pytest.fixture
def corpus(pg, tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `5000`\n\nPreview port.\n")
    b.commit("v1", day(2021, 11, 6))
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `4173`\n\nPreview port.\n")
    b.commit("v2", day(2022, 1, 16))
    ingest_repo(pg, b.path, str(b.path))
    embed_missing(pg, EMB, str(b.path))
    return str(b.path)


Q = "What was the default of preview.port in December 2021?"


def ask_v(pg, corpus, variant):
    return ask(pg, Q, embedder=EMB, llm=FakeLLM(responder), repo_id=corpus, variant=variant,
               now=day(2023, 1, 1), nli=NLI)  # fmt: skip


def test_temporal_verified_keeps_a_supported_current_answer(pg, corpus):
    r = ask_v(pg, corpus, "temporal_verified")
    assert "5000" in r.answer.text and r.verification.action == "keep"
    assert [v.label for v in r.verification.verdicts] == ["supported_current"]
    assert "verification" in r.timings_ms


def test_verified_variant_needs_an_nli_model(pg, corpus):
    with pytest.raises(ValueError, match="NLI"):
        ask(pg, Q, embedder=EMB, llm=FakeLLM(responder), repo_id=corpus,
            variant="temporal_verified")  # fmt: skip


def test_harness_records_claims_and_scores_claim_metrics(pg, corpus, tmp_path):
    ref = {"source_path": "p.md", "section_path": "Preview > preview.port", "chunk_id": 0}
    q = {"id": "past", "type": "point_in_time", "question": Q,
         "as_of": "2021-12-31T23:59:59.999999+00:00", "answerable": True, "gold_answer": "5000",
         "gold_tokens": ["5000"], "stale_tokens": ["4173"], "gold_refs": [ref], "split": "dev",
         "now": "2023-01-01T00:00:00+00:00", "flags": []}  # fmt: skip
    dataset = tmp_path / "q.jsonl"
    dataset.write_text(json.dumps(q) + "\n", "utf-8")
    variants = ("plain", "temporal", "plain_verified", "temporal_verified")
    cfg = RunConfig("v", dataset, "dev", variants, corpus)
    run_dir = run(pg, cfg, embedder=EMB, llm=FakeLLM(responder), nli=NLI,
                  runs_dir=tmp_path / "runs")  # fmt: skip

    records = {
        json.loads(x)["variant"]: json.loads(x)
        for x in (run_dir / "outputs.jsonl").read_text("utf-8").splitlines()
    }
    assert set(records) == set(variants)
    assert records["temporal"]["verification"] is None and records["temporal"]["final_claims"]
    assert records["temporal_verified"]["verification"]["action"] == "keep"
    meta = json.loads((run_dir / "meta.json").read_text("utf-8"))
    assert meta["nli_model"] == "keyword-nli" and meta["threshold"] == 0.5

    _, results = score_run(run_dir, dataset)
    v = results["variants"]
    assert v["temporal_verified"]["unsupported_claim_rate"]["value"] == 0.0
    assert v["temporal_verified"]["faithful_but_stale_rate"]["value"] == 0.0
    assert v["temporal_verified"]["verification_actions"] == {"keep": 1}
    # plain retrieval may cite the newer version: if so, the claim is faithful but stale
    plain_claims = records["plain"]["final_claims"]
    if any("4173" in c["text"] for c in plain_claims):
        assert v["plain"]["faithful_but_stale_rate"]["value"] > 0
