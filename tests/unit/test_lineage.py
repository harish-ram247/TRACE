from app.ingest.chunker import Section, content_hash
from app.ingest.lineage import OpenChunk, match_sections


def sec(path, text):
    return Section(path, text, content_hash(text))


def old(id_, path, text):
    return OpenChunk(id_, id_ * 10, path, content_hash(text), text)


def kinds(matches):
    return sorted((m.kind, m.moved) for m in matches)


def test_same_path_same_text_is_unchanged():
    m = match_sections([old(1, "A", "limit is 100")], [sec("A", "limit is 100")])
    assert [x.kind for x in m] == ["unchanged"]


def test_same_path_new_text_is_changed_and_keeps_lineage():
    m = match_sections([old(1, "A", "limit is 100")], [sec("A", "limit is 500")])
    assert m[0].kind == "changed" and m[0].old.lineage_id == 10 and not m[0].moved


def test_identical_text_under_renamed_heading_is_matched():
    m = match_sections([old(1, "Old name", "same body here")], [sec("New name", "same body here")])
    assert kinds(m) == [("changed", True)]
    assert m[0].similarity == 1.0


def test_renamed_and_slightly_edited_section_is_matched_by_similarity():
    body_old = "The service retries failed requests three times with exponential backoff."
    body_new = "The service retries failed requests four times with exponential backoff."
    m = match_sections([old(1, "Retries", body_old)], [sec("Retry policy", body_new)])
    assert kinds(m) == [("changed", True)]
    assert 0.8 <= m[0].similarity < 1.0


def test_unrelated_sections_are_added_and_removed():
    m = match_sections(
        [old(1, "Gone", "completely different text about storage")],
        [sec("Fresh", "nothing in common regarding networking at all")],
    )
    assert kinds(m) == [("added", False), ("removed", False)]


def test_greedy_matching_pairs_each_old_chunk_once():
    a = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    b = "alpha beta gamma delta epsilon zeta eta theta iota lambda"
    m = match_sections([old(1, "X", a)], [sec("Y", a), sec("Z", b)])
    moved = [x for x in m if x.kind == "changed"]
    assert len(moved) == 1 and moved[0].new.section_path == "Y"  # exact twin wins
    assert sum(1 for x in m if x.kind == "added") == 1


def test_threshold_is_respected():
    a = "one two three four five six seven eight nine ten"
    b = "one two three four five six alpha beta gamma delta"
    strict = match_sections([old(1, "A", a)], [sec("B", b)], threshold=0.95)
    assert sorted(x.kind for x in strict) == ["added", "removed"]
