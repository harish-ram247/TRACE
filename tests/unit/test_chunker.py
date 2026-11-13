from app.ingest.chunker import content_hash, parse_sections


def paths(md, **kw):
    return [s.section_path for s in parse_sections(md, **kw)]


def test_heading_trail_becomes_section_path():
    md = "# Limits\n\nIntro.\n\n## Rate limits\n\n100 per minute.\n\n## Quotas\n\nDaily quota.\n"
    assert paths(md) == ["Limits", "Limits > Rate limits", "Limits > Quotas"]


def test_text_before_first_heading_is_intro():
    assert paths("Some preface.\n\n# Title\n\nBody.\n") == ["(intro)", "Title"]


def test_heading_without_body_is_skipped():
    md = "# Guide\n\n## Setup\n\nDo this.\n"
    assert paths(md) == ["Guide > Setup"]


def test_duplicate_headings_get_numbered():
    md = "# A\n\n## Notes\n\none\n\n## Notes\n\ntwo\n"
    assert paths(md) == ["A > Notes", "A > Notes #2"]


def test_hash_lines_inside_code_fences_are_not_headings():
    md = "# Title\n\n```bash\n# a comment, not a heading\necho hi\n```\n"
    sections = parse_sections(md)
    assert [s.section_path for s in sections] == ["Title"]
    assert "# a comment" in sections[0].text


def test_setext_headings_are_recognised():
    md = "Title\n=====\n\nBody text.\n\nSub\n---\n\nMore text.\n"
    assert paths(md) == ["Title", "Title > Sub"]


def test_front_matter_is_dropped():
    md = "---\ntitle: x\n---\n# Real\n\nBody.\n"
    sections = parse_sections(md)
    assert [s.section_path for s in sections] == ["Real"]
    assert "title: x" not in sections[0].text


def test_crlf_line_endings_give_same_result():
    lf = "# T\n\nBody one.\n\n## U\n\nBody two.\n"
    crlf = lf.replace("\n", "\r\n")
    assert parse_sections(lf) == parse_sections(crlf)


def test_whitespace_only_changes_do_not_change_the_hash():
    assert content_hash("a  b\n\n c") == content_hash("a b c")
    assert content_hash("100 per minute") != content_hash("500 per minute")


def test_long_section_is_split_on_paragraph_boundaries():
    para = " ".join(["word"] * 40)
    md = "# Long\n\n" + "\n\n".join([para] * 5)
    parts = parse_sections(md, max_words=100)
    assert [s.section_path for s in parts] == ["Long [part 1]", "Long [part 2]", "Long [part 3]"]
    assert all(len(s.text.split()) <= 100 + 5 for s in parts)  # heading words may add a few


def test_fenced_code_block_is_never_split():
    code = "```\n" + "\n\n".join(["line one two three"] * 30) + "\n```"
    md = f"# Code\n\nIntro.\n\n{code}\n\nOutro.\n"
    parts = parse_sections(md, max_words=20)
    holders = [s for s in parts if "```" in s.text]
    assert len(holders) == 1
    assert holders[0].text.count("```") == 2


def test_empty_document_has_no_sections():
    assert parse_sections("") == []
    assert parse_sections("\n\n   \n") == []
