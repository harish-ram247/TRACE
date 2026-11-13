"""Vite release dates, used to resolve phrases like "before Vite 3" or "in Vite 4.2"."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).with_name("vite_releases.json")

Releases = dict[tuple[int, int], datetime]


def _parse(d: str) -> datetime:
    return datetime.fromisoformat(d).astimezone(UTC)


@lru_cache
def _load(path: str | None) -> tuple[Releases, Releases]:
    data = json.loads(Path(path or _FILE).read_text("utf-8"))
    final: Releases = {}
    pre: Releases = {}
    for version, info in data["releases"].items():
        key = tuple(int(x) for x in version.split("."))
        final[key] = _parse(info["release"])
        if info.get("first_prerelease"):
            pre[key] = _parse(info["first_prerelease"])
    return final, pre


def load_releases(path: str | None = None) -> Releases:
    """Final release date of each vMAJOR.MINOR.0."""
    return _load(path)[0]


def load_prerelease_starts(path: str | None = None) -> Releases:
    """Date of the first alpha/beta/rc tag of each vMAJOR.MINOR.0 that had one."""
    return _load(path)[1]
