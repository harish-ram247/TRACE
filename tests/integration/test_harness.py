"""The harness end to end on a fixture corpus, with the hash embedder and a fake LLM."""

import json
import re

import pytest

from app.core.llm import FakeLLM, LLMError
from app.evaluation.harness import RunConfig, run
from app.evaluation.metrics import score_run
from app.ingest.service import ingest_repo
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import HashEmbedder
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration
EMB = HashEmbedder()
_SOURCE = re.compile(r'<source label="(S\d+)".*?>\n(.*?)\n</source>', re.DOTALL)


def reader(messages):
    for label, text in _SOURCE.findall(messages[-1]["content"]):
        if m := re.search(r"\b(5000|4173)\b", text):
            return f"The default port is {m.group(1)} [{label}]."
    return "NOT_FOUND"


@pytest.fixture
def setup(pg, tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `5000`\n\nPreview port.\n")
    b.commit("v1", day(2021, 11, 6))
    b.write("p.md", "# Preview\n\n## preview.port\n\n- **Default:** `4173`\n\nPreview port.\n")
    b.commit("v2", day(2022, 1, 16))
    repo_id = str(b.path)
    ingest_repo(pg, b.path, repo_id)
    embed_missing(pg, EMB, repo_id)

    ref = {"source_path": "p.md", "section_path": "Preview > preview.port", "chunk_id": 0}
    questions = [
        _q("past", "point_in_time", "in December 2021", "2021-12-31T23:59:59.999999", "5000",
           ["5000"], ["4173"], [ref]),
        _q("now", "current", "now", "2023-01-01T00:00:00", "4173", ["4173"], ["5000"], [ref]),
        _q("early", "unanswerable", "in June 2021", "2021-06-30T23:59:59.999999", "NOT_FOUND",
           [], [], []),
    ]  # fmt: skip
    dataset = tmp_path / "questions.jsonl"
    dataset.write_text("".join(json.dumps(x) + "\n" for x in questions), "utf-8")
    return repo_id, dataset


def _q(qid, qtype, phrase, as_of, gold, gold_tokens, stale_tokens, refs):
    return {
        "id": qid,
        "type": qtype,
        "question": f"What was the default of preview.port {phrase}?",
        "as_of": as_of + "+00:00",
        "answerable": qtype != "unanswerable",
        "gold_answer": gold,
        "gold_tokens": gold_tokens,
        "stale_tokens": stale_tokens,
        "gold_refs": refs,
        "split": "dev",
        "now": "2023-01-01T00:00:00+00:00",
        "flags": [],
    }


def config(repo_id, dataset, run_id="r1"):
    return RunConfig(run_id, dataset, "dev", ("plain", "temporal"), repo_id)


def test_run_saves_outputs_and_scores_temporal_above_plain(pg, setup, tmp_path):
    repo_id, dataset = setup
    run_dir = run(pg, config(repo_id, dataset), embedder=EMB, llm=FakeLLM(reader),
                  runs_dir=tmp_path / "runs")  # fmt: skip
    lines = (run_dir / "outputs.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 6
    meta = json.loads((run_dir / "meta.json").read_text("utf-8"))
    assert meta["variants"] == ["plain", "temporal"] and meta["llm_model"] == "fake-llm"

    _, results = score_run(run_dir, dataset)
    temporal = results["variants"]["temporal"]
    assert temporal["accuracy"]["value"] == 1.0
    assert temporal["retrieval_recall_at_k"]["value"] == 1.0
    assert temporal["parse_agreement"]["value"] == 1.0
    plain = results["variants"]["plain"]
    assert plain["abstention_recall"]["value"] == 0.0  # plain RAG answers the unanswerable one
    assert results["paired"]["accuracy_difference"] > 0


def test_run_resumes_without_repeating_work(pg, setup, tmp_path):
    repo_id, dataset = setup
    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] == 3:
            raise LLMError("quota exhausted")
        return reader(messages)

    class Flaky(FakeLLM):
        def complete(self, messages, **kw):
            return super().complete(messages, **kw)

    runs = tmp_path / "runs"
    first = run(pg, config(repo_id, dataset), embedder=EMB, llm=Flaky(flaky), runs_dir=runs)
    partial = len((first / "outputs.jsonl").read_text("utf-8").splitlines())
    assert 0 < partial < 6

    second = run(pg, config(repo_id, dataset), embedder=EMB, llm=FakeLLM(reader), runs_dir=runs)
    lines = (second / "outputs.jsonl").read_text("utf-8").splitlines()
    keys = {(json.loads(x)["question_id"], json.loads(x)["variant"]) for x in lines}
    assert len(lines) == 6 and len(keys) == 6


def test_changed_dataset_needs_a_new_run_id(pg, setup, tmp_path):
    repo_id, dataset = setup
    runs = tmp_path / "runs"
    run(pg, config(repo_id, dataset), embedder=EMB, llm=FakeLLM(reader), runs_dir=runs)
    dataset.write_text(dataset.read_text("utf-8") + "\n", "utf-8")
    with pytest.raises(RuntimeError, match="dataset changed"):
        run(pg, config(repo_id, dataset), embedder=EMB, llm=FakeLLM(reader), runs_dir=runs)
