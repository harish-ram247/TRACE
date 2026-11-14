import json

from app.evaluation.metrics import (
    aggregate,
    load_manual,
    paired_difference,
    score_record,
    write_report,
)

AS_OF = "2021-12-31T23:59:59.999999+00:00"
REF = {
    "source_path": "docs/config/index.md",
    "section_path": "Preview > preview.port",
    "chunk_id": 1,
}


def q(qid="q1", qtype="point_in_time", answerable=True, flags=()):
    return {
        "id": qid,
        "type": qtype,
        "question": "What was preview.port in 2021?",
        "as_of": AS_OF,
        "answerable": answerable,
        "gold_answer": "5000" if answerable else "NOT_FOUND",
        "gold_tokens": ["5000"] if answerable else [],
        "stale_tokens": ["4173"] if answerable else [],
        "gold_refs": [REF] if answerable else [],
        "flags": list(flags),
    }


def hit(start, end, cid=1, section="Preview > preview.port"):
    return {"chunk_id": cid, "lineage_id": 9, "source_path": "docs/config/index.md",
            "section_path": section, "valid_from": start, "valid_until": end}  # fmt: skip


OLD = hit("2021-11-06T00:00:00+00:00", "2022-01-16T00:00:00+00:00", cid=1)
NEW = hit("2022-01-16T00:00:00+00:00", None, cid=2)


def rec(answer, variant="temporal", hits=(OLD,), cited=(1,), not_found=False, as_of=AS_OF):
    return {
        "question_id": "q1", "variant": variant, "answer": answer, "not_found": not_found,
        "cited_chunk_ids": list(cited), "invalid_citations": [], "hits": list(hits),
        "time": {"as_of": as_of} if variant == "temporal" else None, "cached": False,
        "timings_ms": {"time_parse": 1, "retrieval": 20, "generation": 900},
    }  # fmt: skip


def test_correct_answer_with_gold_retrieved_and_cited():
    s = score_record(q(), rec("The default was 5000 [S1]."), {})
    assert s.correct and not s.stale and s.gold_retrieved and s.cited_gold and s.parse_ok
    assert s.category is None and s.latency_ms == 921


def test_stale_answer_with_both_versions_in_context_is_f2():
    s = score_record(q(), rec("It is 4173 [S2].", variant="plain", hits=(NEW, OLD), cited=(2,)), {})
    assert not s.correct and s.stale and s.wrong_version_1
    assert s.category.startswith("F2")


def test_stale_answer_with_only_wrong_version_is_f1_and_retrieval_miss_is_f4():
    s = score_record(q(), rec("It is 4173.", hits=(NEW,), cited=()), {})
    assert s.category.startswith("F1") and s.gold_retrieved is False
    s = score_record(q(), rec("Something else.", hits=(hit(AS_OF[:10], None, 5, "Other"),)), {})
    assert s.category.startswith("F4")


def test_abstention_and_parse_errors():
    s = score_record(q(), rec("NOT_FOUND", not_found=True), {})
    assert s.category == "F9 over-abstention despite gold retrieved"
    s = score_record(q(), rec("5000", as_of="2022-06-01T00:00:00+00:00"), {})
    assert s.correct and s.parse_ok is False  # right answer, wrong parse: still counted correct
    s = score_record(q(), rec("4173", as_of="2022-06-01T00:00:00+00:00"), {})
    assert s.category == "F3 temporal parse error"
    s = score_record(q(answerable=False), rec("It was 5000."), {})
    assert s.category.startswith("F10")
    assert score_record(q(answerable=False), rec("NOT_FOUND", not_found=True), {}).correct


def test_manual_override_wins(tmp_path):
    path = tmp_path / "manual_checks.csv"
    path.write_text("question_id,variant,correct,note\nq1,temporal,yes,ok by hand\n", "utf-8")
    manual = load_manual(path)
    s = score_record(q(), rec("It is 4173."), manual)
    assert s.correct and s.manual and not s.auto_correct


def test_aggregate_rates_and_intervals():
    items = [score_record(q(), rec("5000"), {}), score_record(q(), rec("4173"), {})]
    res = aggregate(items)["variants"]["temporal"]
    assert res["accuracy"]["value"] == 0.5 and res["accuracy"]["n"] == 2
    lo, hi = res["accuracy"]["ci"]
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0
    assert res["stale_answer_rate"]["value"] == 0.5


def test_paired_difference_counts_disagreements():
    plain = [score_record(q(qid), rec("4173", variant="plain"), {}) for qid in ("a", "b")]
    temporal = [score_record(q(qid), rec("5000"), {}) for qid in ("a", "b")]
    for s, qid in zip(plain + temporal, ["a", "b", "a", "b"], strict=True):
        s.question_id = qid
    d = paired_difference(plain, temporal)
    assert d["accuracy_difference"] == 1.0 and d["only_b_correct"] == 2 and d["n"] == 2


def test_report_is_written(tmp_path):
    items = [
        score_record(q(), rec("5000"), {}),
        score_record(q(), rec("4173", variant="plain"), {}),
    ]
    meta = {"run_id": "r", "split": "dev", "dataset": "d", "dataset_sha256": "0" * 64,
            "llm_model": "m", "prompt_version": "p", "embedding_model": "e", "top_k": 5,
            "git_commit": "abc"}  # fmt: skip
    path = write_report(tmp_path, aggregate(items), meta)
    text = path.read_text("utf-8")
    assert "Temporal minus plain" in text and "| Answer accuracy (all) |" in text
    assert json.loads((tmp_path / "results.json").read_text("utf-8"))["paired"]["n"] == 1
