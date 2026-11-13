"""Build throwaway git repositories with controlled commit dates for tests.

Identity and signing are passed per command with -c, so the developer's own git
configuration is never touched.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def day(year: int, month: int, d: int, hour: int = 0) -> datetime:
    return datetime(year, month, d, hour, tzinfo=UTC)


class RepoBuilder:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.run("init", "-q", "-b", "main")

    def run(self, *args: str, when: datetime | None = None) -> str:
        env = dict(os.environ)
        if when is not None:
            iso = when.isoformat()
            env["GIT_AUTHOR_DATE"] = iso
            env["GIT_COMMITTER_DATE"] = iso
        proc = subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.autocrlf=false",
                "-C",
                str(self.path),
                *args,
            ],
            capture_output=True,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}")
        return proc.stdout.decode()

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def remove(self, rel: str) -> None:
        (self.path / rel).unlink()

    def move(self, old: str, new: str) -> None:
        (self.path / new).parent.mkdir(parents=True, exist_ok=True)
        self.run("mv", old, new)

    def commit(self, message: str, when: datetime) -> str:
        self.run("add", "-A")
        self.run("commit", "-q", "-m", message, when=when)
        return self.run("rev-parse", "HEAD").strip()
