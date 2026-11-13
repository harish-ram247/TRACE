"""End-to-end ingestion into PostgreSQL. Needs a migrated database (alembic upgrade head)."""

import random

import pytest

from app.ingest.chunker import parse_sections
from app.ingest.invariants import check_invariants
from app.ingest.service import ingest_repo
from tests.fixtures.repo_builder import RepoBuilder, day

pytestmark = pytest.mark.integration

LIMITS_V1 = "# Limits\n\nThe API allows 100 requests per minute.\n"
LIMITS_V2 = "# Limits\n\nThe API allows 500 requests per minute.\n"


def versions(pg, repo_id, path):
    return pg.execute(
        """
        SELECT c.section_path, c.text, lower(c.valid), upper(c.valid), c.lineage_id,
               c.supersedes_id, c.id
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s AND d.source_path = %s ORDER BY c.id
        """,
        (repo_id, path),
    ).fetchall()


def texts_valid_at(pg, repo_id, when):
    rows = pg.execute(
        """
        SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s AND c.valid @> %s::timestamptz ORDER BY c.text
        """,
        (repo_id, when),
    ).fetchall()
    return [r[0] for r in rows]


@pytest.fixture
def repo(tmp_path):
    return RepoBuilder(tmp_path / "repo")


def run(pg, repo, **kw):
    return ingest_repo(pg, repo.path, str(repo.path), **kw)


def test_modification_creates_a_second_version_in_the_same_lineage(pg, repo):
    repo.write("limits.md", LIMITS_V1)
    repo.commit("v1", day(2023, 1, 1))
    repo.write("limits.md", LIMITS_V2)
    repo.commit("v2", day(2024, 2, 1))
    run(pg, repo)

    first, second = versions(pg, str(repo.path), "limits.md")
    assert first[4] == second[4]  # same lineage
    assert first[2] == day(2023, 1, 1) and first[3] == day(2024, 2, 1)
    assert second[2] == day(2024, 2, 1) and second[3] is None
    assert second[5] == first[6]  # supersedes
    assert "100" in texts_valid_at(pg, str(repo.path), day(2023, 6, 1))[0]
    assert "500" in texts_valid_at(pg, str(repo.path), day(2024, 6, 1))[0]
    assert texts_valid_at(pg, str(repo.path), day(2022, 1, 1)) == []
    assert check_invariants(pg, str(repo.path)) == []


def test_unchanged_sections_are_not_versioned(pg, repo):
    repo.write("g.md", "# G\n\n## One\n\nstays the same\n\n## Two\n\nold value\n")
    repo.commit("c1", day(2023, 1, 1))
    repo.write("g.md", "# G\n\n## One\n\nstays the same\n\n## Two\n\nnew value\n")
    repo.commit("c2", day(2023, 2, 1))
    run(pg, repo)

    rows = versions(pg, str(repo.path), "g.md")
    by_path = {}
    for r in rows:
        by_path.setdefault(r[0], []).append(r)
    assert len(by_path["G > One"]) == 1 and by_path["G > One"][0][3] is None
    assert len(by_path["G > Two"]) == 2


def test_deleting_a_file_closes_its_chunks(pg, repo):
    repo.write("a.md", LIMITS_V1)
    repo.commit("add", day(2023, 1, 1))
    repo.remove("a.md")
    repo.commit("delete", day(2023, 5, 1))
    run(pg, repo)

    (row,) = versions(pg, str(repo.path), "a.md")
    assert row[3] == day(2023, 5, 1)
    assert texts_valid_at(pg, str(repo.path), day(2023, 6, 1)) == []
    assert check_invariants(pg, str(repo.path)) == []


def test_file_rename_keeps_document_and_does_not_duplicate_chunks(pg, repo):
    repo.write("old.md", LIMITS_V1)
    repo.commit("add", day(2023, 1, 1))
    repo.move("old.md", "new.md")
    repo.commit("rename", day(2023, 2, 1))
    run(pg, repo)

    assert versions(pg, str(repo.path), "old.md") == []
    (row,) = versions(pg, str(repo.path), "new.md")
    assert row[2] == day(2023, 1, 1) and row[3] is None


def test_renamed_heading_continues_the_lineage(pg, repo):
    body = "The service retries failed requests three times with exponential backoff."
    repo.write("r.md", f"# Retries\n\n{body}\n")
    repo.commit("c1", day(2023, 1, 1))
    repo.write("r.md", f"# Retry policy\n\n{body}\n")
    repo.commit("c2", day(2023, 2, 1))
    run(pg, repo)

    first, second = versions(pg, str(repo.path), "r.md")
    assert first[4] == second[4]
    assert (first[0], second[0]) == ("Retries", "Retry policy")


def test_rerunning_is_idempotent_and_picks_up_new_commits(pg, repo):
    repo.write("a.md", LIMITS_V1)
    repo.commit("v1", day(2023, 1, 1))
    first = run(pg, repo)
    assert first.commits_seen == 1

    again = run(pg, repo)
    assert again.commits_seen == 0 and again.chunks_added == 0
    assert len(versions(pg, str(repo.path), "a.md")) == 1

    repo.write("a.md", LIMITS_V2)
    repo.commit("v2", day(2023, 2, 1))
    resumed = run(pg, repo)
    assert resumed.commits_seen == 1 and resumed.resumed_after is not None
    assert len(versions(pg, str(repo.path), "a.md")) == 2


def test_commits_with_the_same_timestamp_never_store_an_empty_version(pg, repo):
    when = day(2023, 1, 1)
    repo.write("a.md", "# A\n\nfirst draft\n")
    repo.commit("c1", when)
    repo.write("a.md", "# A\n\nsecond draft\n")
    repo.commit("c2", when)
    repo.write("a.md", "# A\n\nfinal text\n")
    repo.commit("c3", day(2023, 2, 1))
    run(pg, repo)

    rows = versions(pg, str(repo.path), "a.md")
    assert len(rows) == 2  # "first draft" was never valid for any time, so it is not stored
    assert [r[1].split("\n")[-1] for r in rows] == ["second draft", "final text"]
    assert check_invariants(pg, str(repo.path)) == []


def test_non_markdown_files_are_ignored(pg, repo):
    repo.write("data.txt", "# Not markdown\n\nignored\n")
    repo.write("a.md", LIMITS_V1)
    repo.commit("both", day(2023, 1, 1))
    run(pg, repo)
    assert versions(pg, str(repo.path), "data.txt") == []
    assert len(versions(pg, str(repo.path), "a.md")) == 1


# ---- time travel: the database must reproduce every historical state of the repository ------


def _render(title, sections):
    out = [f"# {title}", ""]
    for name, body in sections.items():
        out += [f"## {name}", "", body, ""]
    return "\n".join(out)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_random_history_is_reproduced_exactly_at_every_commit(pg, repo, seed):
    rng = random.Random(seed)
    files: dict[str, dict[str, str]] = {}
    counter = 0
    expected = []  # (commit time, sorted section texts of the whole repo at that commit)

    for step in range(14):
        counter += 1
        ops = ["add_file"] if not files else ["add_file", "edit", "add_section", "drop_section"]
        if files:
            ops += ["delete_file", "rename_file"]
        op = rng.choice(ops)
        if op == "add_file":
            name = f"f{counter}.md"
            files[name] = {"Intro": f"Fresh text {counter} for {name}."}
        else:
            name = rng.choice(sorted(files))
            if op == "edit":
                sec = rng.choice(sorted(files[name]))
                files[name][sec] = f"Edited value {counter} in {sec}."
            elif op == "add_section":
                files[name][f"S{counter}"] = f"New section body {counter}."
            elif op == "drop_section":
                if len(files[name]) > 1:
                    del files[name][rng.choice(sorted(files[name]))]
                else:  # never leave a step without a change
                    files[name]["Intro"] = f"Edited value {counter} in Intro."
            elif op == "delete_file":
                del files[name]
            elif op == "rename_file":
                new = f"r{counter}.md"
                files[new] = files.pop(name)

        # sync the working tree with the model
        for existing in list((repo.path).glob("*.md")):
            existing.unlink()
        for name, secs in files.items():
            repo.write(name, _render(name, secs))
        when = day(2023, 1, 1 + step)
        repo.commit(f"step {step}: {op}", when)

        texts = sorted(
            s.text for n, secs in files.items() for s in parse_sections(_render(n, secs))
        )
        expected.append((when, texts))

    run(pg, repo)
    for when, texts in expected:
        assert texts_valid_at(pg, str(repo.path), when) == texts, f"mismatch at {when}"
    assert check_invariants(pg, str(repo.path)) == []
