"""Decide how the sections of a new file version relate to the chunks that are currently open.

Pure logic, no database. Matching order:
1. Same section path: the same passage (unchanged if the hash matches, otherwise a new version).
2. Identical text under a different path: the heading was renamed or the section moved.
3. Similar text (ratio >= threshold) under a different path: moved or renamed and also edited.
Anything left over in the old set is removed, anything left over in the new set is added.

Known limitation: a section that is renamed AND heavily rewritten in one commit looks like a
removal plus an addition, so its lineage is not continued.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from app.ingest.chunker import Section, normalise

DEFAULT_SIMILARITY_THRESHOLD = 0.8


@dataclass(frozen=True)
class OpenChunk:
    id: int
    lineage_id: int
    section_path: str
    content_hash: str
    text: str


@dataclass(frozen=True)
class Match:
    kind: Literal["unchanged", "changed", "added", "removed"]
    old: OpenChunk | None = None
    new: Section | None = None
    similarity: float = 1.0
    moved: bool = False  # the section path differs between old and new


def _similarity(a: str, b: str) -> float:
    matcher = SequenceMatcher(None, normalise(a), normalise(b), autojunk=False)
    return matcher.ratio()


def match_sections(
    open_chunks: list[OpenChunk],
    sections: list[Section],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[Match]:
    matches: list[Match] = []
    old_by_path = {c.section_path: c for c in open_chunks}
    used_old: set[int] = set()
    unmatched_new: list[Section] = []

    # 1. same path
    for sec in sections:
        old = old_by_path.get(sec.section_path)
        if old is None:
            unmatched_new.append(sec)
            continue
        used_old.add(old.id)
        if old.content_hash == sec.content_hash:
            matches.append(Match("unchanged", old, sec))
        else:
            matches.append(Match("changed", old, sec, _similarity(old.text, sec.text)))

    leftovers = [c for c in open_chunks if c.id not in used_old]

    # 2. identical text, different path
    still_new: list[Section] = []
    for sec in unmatched_new:
        twin = next((c for c in leftovers if c.content_hash == sec.content_hash), None)
        if twin is None:
            still_new.append(sec)
            continue
        leftovers.remove(twin)
        matches.append(Match("changed", twin, sec, 1.0, moved=True))

    # 3. similar text, different path (greedy by similarity)
    candidates: list[tuple[float, int, int]] = []
    for j, sec in enumerate(still_new):
        for i, old in enumerate(leftovers):
            sm = SequenceMatcher(None, normalise(old.text), normalise(sec.text), autojunk=False)
            if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                continue
            ratio = sm.ratio()
            if ratio >= threshold:
                candidates.append((ratio, i, j))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))

    taken_old: set[int] = set()
    taken_new: set[int] = set()
    for ratio, i, j in candidates:
        if i in taken_old or j in taken_new:
            continue
        taken_old.add(i)
        taken_new.add(j)
        matches.append(Match("changed", leftovers[i], still_new[j], ratio, moved=True))

    # 4. leftovers
    for j, sec in enumerate(still_new):
        if j not in taken_new:
            matches.append(Match("added", None, sec))
    for i, old in enumerate(leftovers):
        if i not in taken_old:
            matches.append(Match("removed", old, None))
    return matches
