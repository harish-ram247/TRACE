from app.ingest.git_walker import FileChange, is_ancestor, iter_commits, read_file
from tests.fixtures.repo_builder import RepoBuilder, day


def build(tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("docs/a.md", "# A\n\nfirst\n")
    b.write("notes.txt", "ignored\n")
    c1 = b.commit("add a", day(2023, 1, 1))
    b.write("docs/a.md", "# A\n\nsecond\n")
    c2 = b.commit("edit a", day(2023, 2, 1))
    b.move("docs/a.md", "docs/b.md")
    c3 = b.commit("rename a to b", day(2023, 3, 1))
    b.remove("docs/b.md")
    c4 = b.commit("delete b", day(2023, 4, 1))
    return b, [c1, c2, c3, c4]


def test_commits_are_oldest_first_with_utc_dates(tmp_path):
    b, shas = build(tmp_path)
    commits = list(iter_commits(b.path))
    assert [c.sha for c in commits] == shas
    assert [c.committed_at.isoformat() for c in commits][0] == "2023-01-01T00:00:00+00:00"


def test_change_types_and_filter(tmp_path):
    b, _ = build(tmp_path)
    commits = list(iter_commits(b.path))
    assert commits[0].changes == [FileChange("add", "docs/a.md")]  # notes.txt filtered out
    assert commits[1].changes == [FileChange("modify", "docs/a.md")]
    assert commits[2].changes == [FileChange("rename", "docs/b.md", "docs/a.md")]
    assert commits[3].changes == [FileChange("delete", "docs/b.md")]


def test_after_skips_already_seen_commits(tmp_path):
    b, shas = build(tmp_path)
    rest = list(iter_commits(b.path, after=shas[1]))
    assert [c.sha for c in rest] == shas[2:]


def test_rename_across_the_filter_boundary_becomes_add_or_delete(tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("x.txt", "# T\n\nbody text here\n")
    b.commit("txt", day(2023, 1, 1))
    b.move("x.txt", "x.md")
    b.commit("to md", day(2023, 2, 1))
    b.move("x.md", "x.dat")
    b.commit("away", day(2023, 3, 1))
    commits = list(iter_commits(b.path))
    assert commits[1].changes == [FileChange("add", "x.md")]
    assert commits[2].changes == [FileChange("delete", "x.md")]


def test_merge_commit_is_one_event_against_its_first_parent(tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("a.md", "# A\n\nbase\n")
    b.commit("base", day(2023, 1, 1))
    b.run("checkout", "-q", "-b", "feature")
    b.write("feat.md", "# F\n\nfeature work\n")
    b.commit("feature", day(2023, 1, 2))
    b.run("checkout", "-q", "main")
    b.write("a.md", "# A\n\nmain edit\n")
    b.commit("main edit", day(2023, 1, 3))
    b.run("merge", "--no-ff", "-q", "feature", "-m", "merge", when=day(2023, 1, 4))

    commits = list(iter_commits(b.path))
    assert [c.changes for c in commits][-1] == [FileChange("add", "feat.md")]
    assert len(commits) == 3  # base, main edit, merge (the feature commit is not walked)


def test_pathspecs_limit_commits_and_changes(tmp_path):
    b = RepoBuilder(tmp_path / "repo")
    b.write("docs/a.md", "# A\n\nfirst\n")
    b.write("other/o.md", "# O\n\nfirst\n")
    c1 = b.commit("both", day(2023, 1, 1))
    b.write("other/o.md", "# O\n\nsecond\n")
    b.commit("other only", day(2023, 2, 1))
    b.write("docs/a.md", "# A\n\nsecond\n")
    c3 = b.commit("docs only", day(2023, 3, 1))

    commits = list(iter_commits(b.path, pathspecs=["docs/"]))
    assert [c.sha for c in commits] == [c1, c3]
    assert commits[0].changes == [FileChange("add", "docs/a.md")]


def test_read_file_and_is_ancestor(tmp_path):
    b, shas = build(tmp_path)
    assert read_file(b.path, shas[0], "docs/a.md") == "# A\n\nfirst\n"
    assert is_ancestor(b.path, shas[0], shas[3])
    assert not is_ancestor(b.path, shas[3], shas[0])
