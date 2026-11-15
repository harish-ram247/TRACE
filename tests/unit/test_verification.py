import json
from datetime import UTC, datetime

from app.core.llm import FakeLLM
from app.generation.answer import Answer
from app.retrieval.search import Hit
from app.verification.claims import Claim, extract_claims, sentence_fallback
from app.verification.nli import KeywordNLI, windows
from app.verification.verify import verified_answer, verify_claims


def d(y, m=1, day=1):
    return datetime(y, m, day, tzinfo=UTC)


OLD = Hit(
    1, 7, "docs/config/index.md", "Preview > preview.port", "- **Default:** `5000` Preview port.",
    d(2021, 11), d(2022, 1, 16), 0.03, 1, 1,
)  # fmt: skip
NEW = Hit(
    2, 7, "docs/config/preview-options.md", "Preview > preview.port",
    "- **Default:** `4173` Preview port.", d(2022, 1, 16), None, 0.02, 2, 2,
)  # fmt: skip
AS_OF = d(2021, 12, 31)
NLI = KeywordNLI()


# ---- windows -----------------------------------------------------------------------------
def test_short_text_is_one_window_long_text_is_split_with_overlap():
    assert windows("one two three") == ["one two three"]
    long = " ".join(f"Sentence {i} has some words in it." for i in range(80))
    parts = windows(long, size=60, overlap=20)
    assert len(parts) > 1
    assert all(len(p.split()) <= 90 for p in parts)


# ---- claim extraction --------------------------------------------------------------------
def test_llm_claims_are_validated():
    reply = json.dumps({"claims": [{"text": "The default of `preview.port` is 5000.",
                                    "sources": ["S1", "bogus"]}, {"text": "  "}]})  # fmt: skip
    ex = extract_claims(FakeLLM(lambda m: reply), "It is 5000 [S1].")
    assert ex.method == "llm"
    assert ex.claims == [Claim("The default of `preview.port` is 5000.", ["S1"])]


def test_malformed_output_is_retried_then_falls_back_to_sentences():
    calls = []

    def bad(messages):
        calls.append(messages)
        return "not json"

    ex = extract_claims(FakeLLM(bad), "The port is `5000` [S1]. It was changed later [S2, S1].")
    assert len(calls) == 2 and ex.method == "sentence_fallback"
    assert ex.claims == [
        Claim("The port is `5000`.", ["S1"]),
        Claim("It was changed later.", ["S2", "S1"]),
    ]


def test_not_found_has_no_claims():
    llm = FakeLLM(lambda m: "{}")
    assert extract_claims(llm, "NOT_FOUND").claims == [] and llm.calls == []


def test_sentence_fallback_handles_uncited_sentences():
    assert sentence_fallback("Plain fact.") == [Claim("Plain fact.", [])]


# ---- labels ------------------------------------------------------------------------------
def test_labels_current_outdated_unsupported():
    claims = [
        Claim("The default of `preview.port` is `5000`.", ["S1"]),
        Claim("The default of `preview.port` is `4173`.", ["S2"]),
        Claim("The default of `preview.port` is `9999`.", ["S1"]),
        Claim("It is fast.", []),
    ]
    v = verify_claims(claims, [OLD, NEW], NLI, as_of=d(2021, 12, 31))
    assert [x.label for x in v] == [
        "supported_current", "supported_outdated", "unsupported", "unsupported",
    ]  # fmt: skip
    assert v[1].valid_at_as_of is False and v[1].best_valid_from.startswith("2022-01-16")
    assert v[0].best_chunk_id == 1 and v[3].best_source is None


def test_without_a_date_only_entailment_is_checked():
    v = verify_claims([Claim("Default `4173`.", ["S2"])], [OLD, NEW], NLI, as_of=None)
    assert v[0].label == "supported_current" and v[0].valid_at_as_of is None


def test_a_claim_citing_both_versions_uses_the_valid_one():
    v = verify_claims([Claim("Default `5000`.", ["S2", "S1"])], [OLD, NEW], NLI, d(2021, 12, 1))
    assert v[0].label == "supported_current" and v[0].best_source == "S1"


# ---- policy ------------------------------------------------------------------------------
def scripted(answers: list[str], claims: list[list[dict]]):
    """Fake LLM: generation replies come from `answers`, extraction replies from `claims`."""
    a, c = iter(answers), iter(claims)

    def respond(messages):
        if "split an answer" in messages[0]["content"]:
            return json.dumps({"claims": next(c)})
        return next(a)

    return FakeLLM(respond)


def answer(text):
    return Answer(text, not_found=text == "NOT_FOUND", model="fake")


def run(llm, first, as_of=AS_OF):
    return verified_answer(llm, NLI, "q?", [OLD, NEW], answer(first), as_of=as_of,
                           temporal=True, time_phrase=None)  # fmt: skip


def test_supported_answer_is_kept_with_one_extra_call():
    llm = scripted([], [[{"text": "Default `5000`.", "sources": ["S1"]}]])
    final, rec = run(llm, "It is `5000` [S1].")
    assert rec.action == "keep" and final.text == "It is `5000` [S1]." and rec.extra_llm_calls == 1


def test_unsupported_answer_is_revised_once():
    llm = scripted(
        ["It is `5000` [S1]."],
        [
            [{"text": "Default `4173`.", "sources": ["S2"]}],
            [{"text": "Default `5000`.", "sources": ["S1"]}],
        ],
    )
    final, rec = run(llm, "It is `4173` [S2].")
    assert rec.action == "revised" and final.text == "It is `5000` [S1]."
    assert rec.verdicts[0].label == "supported_outdated"
    revision_prompt = llm.calls[1]["messages"]
    assert (
        revision_prompt[-2]["content"] == "It is `4173` [S2]."
        and "not valid" in revision_prompt[-1]["content"]
    )


def test_if_revision_still_fails_only_supported_claims_are_kept():
    llm = scripted(
        ["Mixed `5000` [S1] and `9999` [S1]."],
        [
            [{"text": "Default `9999`.", "sources": ["S1"]}],
            [
                {"text": "Default `5000`.", "sources": ["S1"]},
                {"text": "Default `9999`.", "sources": ["S1"]},
            ],
        ],
    )  # fmt: skip
    final, rec = run(llm, "It is `9999` [S1].")
    assert rec.action == "dropped_claims"
    assert final.text == "Default `5000`. [S1]" and [c.chunk_id for c in final.citations] == [1]


def test_nothing_supported_means_abstain():
    llm = scripted(["NOT_FOUND"], [[{"text": "Default `9999`.", "sources": ["S1"]}]])
    final, rec = run(llm, "It is `9999` [S1].")
    assert rec.action == "abstained" and final.not_found


def test_not_found_is_not_verified():
    llm = scripted([], [])
    final, rec = run(llm, "NOT_FOUND")
    assert rec.action == "nothing_to_verify" and llm.calls == []
