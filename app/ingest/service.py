"""Turn a repository's git history into versioned chunks with validity intervals.

For every commit (oldest first, first-parent) the changed markdown files are re-parsed into
sections and compared with the chunks currently open for that file:
- unchanged section: nothing happens, its validity simply stays open
- changed section: the old chunk is closed at the commit time and a new one is opened
- removed section / deleted file: the chunk is closed
- new section / new file: a chunk is opened in a new lineage

Each commit is applied in its own transaction together with the progress marker, so a crash can
be resumed and a re-run is idempotent.

Time policy: effective commit time = max(commit time, previous effective time), so validity
never runs backwards. A version that would be valid for zero time (two commits with the same
timestamp) is never stored.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg

from app.ingest import git_walker
from app.ingest.chunker import DEFAULT_MAX_WORDS, Section, parse_sections
from app.ingest.git_walker import CommitChange, FileChange
from app.ingest.lineage import DEFAULT_SIMILARITY_THRESHOLD, OpenChunk, match_sections

log = logging.getLogger(__name__)


class IngestError(RuntimeError):
    pass


@dataclass
class IngestResult:
    run_id: int
    commits_seen: int = 0
    commits_changed: int = 0
    chunks_added: int = 0
    chunks_closed: int = 0
    resumed_after: str | None = None


class _Ingestor:
    def __init__(
        self,
        conn: psycopg.Connection,
        repo: Path,
        repo_id: str,
        max_words: int,
        threshold: float,
        result: IngestResult,
    ):
        self.conn = conn
        self.repo = repo
        self.repo_id = repo_id
        self.max_words = max_words
        self.threshold = threshold
        self.result = result

    # ---- documents -------------------------------------------------------------------------
    def _find_doc(self, path: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM documents WHERE repo_url = %s AND source_path = %s",
            (self.repo_id, path),
        ).fetchone()
        return row[0] if row else None

    def _get_or_create_doc(self, path: str) -> int:
        doc = self._find_doc(path)
        if doc is not None:
            return doc
        return self.conn.execute(
            "INSERT INTO documents (source_path, repo_url) VALUES (%s, %s) RETURNING id",
            (path, self.repo_id),
        ).fetchone()[0]

    # ---- chunks ----------------------------------------------------------------------------
    def _open_chunks(self, doc_id: int) -> list[OpenChunk]:
        rows = self.conn.execute(
            """
            SELECT id, lineage_id, section_path, content_hash, text
            FROM chunks WHERE document_id = %s AND upper_inf(valid) ORDER BY id
            """,
            (doc_id,),
        ).fetchall()
        return [OpenChunk(*r) for r in rows]

    def _close(self, chunk: OpenChunk, at: datetime, sha: str) -> int:
        """Close a chunk at `at`. Returns the id the next version should supersede.

        A chunk that would have zero validity is deleted instead, and its own predecessor
        is returned so the supersession chain stays intact.
        """
        lower, supersedes = self.conn.execute(
            "SELECT lower(valid), supersedes_id FROM chunks WHERE id = %s", (chunk.id,)
        ).fetchone()
        self.result.chunks_closed += 1
        if lower >= at:
            self.conn.execute("DELETE FROM chunks WHERE id = %s", (chunk.id,))
            return supersedes
        self.conn.execute(
            """
            UPDATE chunks SET valid = tstzrange(lower(valid), %s::timestamptz), removed_commit = %s
            WHERE id = %s
            """,
            (at, sha, chunk.id),
        )
        return chunk.id

    def _insert(
        self,
        doc_id: int,
        lineage_id: int,
        section: Section,
        at: datetime,
        sha: str,
        supersedes: int | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO chunks (lineage_id, document_id, section_path, text, content_hash,
                                valid, introduced_commit, supersedes_id)
            VALUES (%s, %s, %s, %s, %s, tstzrange(%s::timestamptz, NULL), %s, %s)
            """,
            (
                lineage_id,
                doc_id,
                section.section_path,
                section.text,
                section.content_hash,
                at,
                sha,
                supersedes,
            ),
        )
        self.result.chunks_added += 1

    def _new_lineage(self) -> int:
        return self.conn.execute("SELECT nextval('lineage_id_seq')").fetchone()[0]

    # ---- applying changes ------------------------------------------------------------------
    def _sync_file(self, doc_id: int, content: str, at: datetime, sha: str) -> None:
        sections = parse_sections(content, self.max_words)
        for m in match_sections(self._open_chunks(doc_id), sections, self.threshold):
            if m.kind == "unchanged":
                continue
            if m.kind == "removed":
                self._close(m.old, at, sha)
            elif m.kind == "added":
                self._insert(doc_id, self._new_lineage(), m.new, at, sha, None)
            else:  # changed
                if m.moved:  # a continued lineage under a different heading is worth a log line
                    log.info(
                        "lineage %s continues: %r -> %r (similarity %.2f, moved=%s)",
                        m.old.lineage_id,
                        m.old.section_path,
                        m.new.section_path,
                        m.similarity,
                        m.moved,
                    )
                supersedes = self._close(m.old, at, sha)
                self._insert(doc_id, m.old.lineage_id, m.new, at, sha, supersedes)

    def _close_document(self, doc_id: int, at: datetime, sha: str) -> None:
        for chunk in self._open_chunks(doc_id):
            self._close(chunk, at, sha)

    def _archive_path(self, doc_id: int, sha: str) -> None:
        """Free a path held by an inactive document so another file can take it."""
        self.conn.execute(
            "UPDATE documents SET source_path = source_path || %s WHERE id = %s",
            (f"#deleted@{sha[:8]}", doc_id),
        )

    def apply_commit(self, commit: CommitChange, at: datetime) -> None:
        sha = commit.sha
        order = {"delete": 0, "rename": 1, "add": 2, "modify": 2}
        for change in sorted(commit.changes, key=lambda c: order[c.change_type]):
            self._apply(change, at, sha)

    def _apply(self, change: FileChange, at: datetime, sha: str) -> None:
        if change.change_type == "delete":
            doc = self._find_doc(change.path)
            if doc is not None:
                self._close_document(doc, at, sha)
            return

        if change.change_type == "rename":
            doc = self._find_doc(change.old_path)
            if doc is None:
                change = FileChange("add", change.path)
            else:
                target = self._find_doc(change.path)
                if target is not None and target != doc:
                    self._archive_path(target, sha)
                self.conn.execute(
                    "UPDATE documents SET source_path = %s WHERE id = %s", (change.path, doc)
                )
                content = git_walker.read_file(self.repo, sha, change.path)
                self._sync_file(doc, content, at, sha)
                return

        doc = self._get_or_create_doc(change.path)
        content = git_walker.read_file(self.repo, sha, change.path)
        self._sync_file(doc, content, at, sha)


def _resume_point(conn: psycopg.Connection, repo_id: str) -> tuple[str, datetime] | None:
    row = conn.execute(
        """
        SELECT last_commit, last_effective_at FROM ingest_runs
        WHERE repo_url = %s AND last_commit IS NOT NULL ORDER BY id DESC LIMIT 1
        """,
        (repo_id,),
    ).fetchone()
    return (row[0], row[1]) if row else None


def ingest_repo(
    conn: psycopg.Connection,
    repo_path: str | Path,
    repo_id: str,
    *,
    path_filter: Callable[[str], bool] = git_walker.is_markdown,
    max_words: int = DEFAULT_MAX_WORDS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    until: str = "HEAD",
    pathspecs: Sequence[str] = (),
) -> IngestResult:
    """Ingest new commits of `repo_path` (identified in the database by `repo_id`)."""
    repo = Path(repo_path)
    resume = _resume_point(conn, repo_id)
    after = resume[0] if resume else None
    previous_at = resume[1] if resume else None
    if after and not git_walker.is_ancestor(repo, after, until):
        raise IngestError(
            f"last ingested commit {after[:8]} is not an ancestor of {until}; "
            "history was rewritten, re-ingest into a fresh repo_id"
        )

    run_id = conn.execute(
        "INSERT INTO ingest_runs (repo_url, repo_ref) VALUES (%s, %s) RETURNING id",
        (repo_id, until),
    ).fetchone()[0]
    result = IngestResult(run_id=run_id, resumed_after=after)
    worker = _Ingestor(conn, repo, repo_id, max_words, similarity_threshold, result)

    try:
        for commit in git_walker.iter_commits(
            repo, after=after, until=until, path_filter=path_filter, pathspecs=pathspecs
        ):
            at = commit.committed_at
            if previous_at is not None and at < previous_at:
                at = previous_at
            with conn.transaction():
                worker.apply_commit(commit, at)
                conn.execute(
                    """
                    UPDATE ingest_runs SET last_commit = %s, last_effective_at = %s,
                                           commits_processed = commits_processed + 1
                    WHERE id = %s
                    """,
                    (commit.sha, at, run_id),
                )
            previous_at = at
            result.commits_seen += 1
            if commit.changes:
                result.commits_changed += 1
    except Exception as exc:
        conn.execute(
            """
            UPDATE ingest_runs SET status = 'failed', finished_at = now(), error = %s
            WHERE id = %s
            """,
            (str(exc)[:2000], run_id),
        )
        raise

    conn.execute(
        "UPDATE ingest_runs SET status = 'done', finished_at = now() WHERE id = %s", (run_id,)
    )
    return result
