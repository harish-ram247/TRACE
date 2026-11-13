"""Walk a git repository's history and report which documentation files changed in each commit.

Uses the `git` command line directly (no extra dependency). History policy: first-parent only, so a
merge commit is one event whose diff is taken against its first parent (see docs/decisions.md).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

ChangeType = Literal["add", "modify", "delete", "rename"]

_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileChange:
    change_type: ChangeType
    path: str
    old_path: str | None = None  # only for renames


@dataclass(frozen=True)
class CommitChange:
    sha: str
    committed_at: datetime  # timezone-aware, UTC
    changes: list[FileChange] = field(default_factory=list)


def is_markdown(path: str) -> bool:
    return path.lower().endswith((".md", ".markdown"))


def _run(repo: Path, *args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        input=input_bytes,
    )


def _git(repo: Path, *args: str) -> bytes:
    proc = _run(repo, *args)
    if proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed: {proc.stderr.decode(errors='replace').strip()}"
        )
    return proc.stdout


@lru_cache(maxsize=32)
def _empty_tree(repo: str) -> str:
    proc = _run(Path(repo), "hash-object", "-t", "tree", "--stdin", input_bytes=b"")
    if proc.returncode != 0:
        raise GitError(proc.stderr.decode(errors="replace").strip())
    return proc.stdout.decode().strip()


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = _run(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise GitError(proc.stderr.decode(errors="replace").strip())


def read_file(repo: Path, sha: str, path: str) -> str:
    """File content as of a commit. Invalid UTF-8 bytes are replaced, not fatal."""
    return _git(repo, "cat-file", "blob", f"{sha}:{path}").decode("utf-8", errors="replace")


def _parse_name_status(raw: bytes, path_filter: Callable[[str], bool]) -> list[FileChange]:
    parts = raw.decode("utf-8", errors="replace").split("\0")
    changes: list[FileChange] = []
    i = 0
    while i < len(parts) and parts[i]:
        code = parts[i][0]
        if code == "R":
            old, new = parts[i + 1], parts[i + 2]
            i += 3
            old_ok, new_ok = path_filter(old), path_filter(new)
            if old_ok and new_ok:
                changes.append(FileChange("rename", new, old))
            elif new_ok:
                changes.append(FileChange("add", new))
            elif old_ok:
                changes.append(FileChange("delete", old))
            continue
        path = parts[i + 1]
        i += 2
        if not path_filter(path):
            continue
        if code == "A":
            changes.append(FileChange("add", path))
        elif code in ("M", "T"):
            changes.append(FileChange("modify", path))
        elif code == "D":
            changes.append(FileChange("delete", path))
    return changes


def iter_commits(
    repo: str | Path,
    *,
    after: str | None = None,
    until: str = "HEAD",
    path_filter: Callable[[str], bool] = is_markdown,
    pathspecs: Sequence[str] = (),
) -> Iterator[CommitChange]:
    """Yield first-parent commits oldest first, each with its relevant file changes.

    `pathspecs` (for example ["docs/"]) limits the walk to commits that touch those paths, which
    is much faster on large repositories. Without it, commits that touch no relevant file are
    still yielded (with an empty change list) so callers can advance their progress marker.
    """
    repo = Path(repo)
    rev_range = f"{after}..{until}" if after else until
    fmt = f"--format=%H{_FIELD_SEP}%P{_FIELD_SEP}%cI{_RECORD_SEP}"
    tail = ["--", *pathspecs] if pathspecs else []
    log = _git(repo, "log", "--first-parent", "--reverse", fmt, rev_range, *tail).decode()

    for record in log.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, committed = record.split(_FIELD_SEP)
        base = parents.split()[0] if parents else _empty_tree(str(repo))
        raw = _git(repo, "diff", "--name-status", "-M", "-z", base, sha, *tail)
        yield CommitChange(
            sha=sha,
            committed_at=datetime.fromisoformat(committed).astimezone(UTC),
            changes=_parse_name_status(raw, path_filter),
        )
