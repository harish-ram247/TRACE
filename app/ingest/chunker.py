"""Split a markdown document into heading-based sections ("chunks").

Rules (see project_plan.md, M3):
- A section runs from a heading to the next heading of any level.
- `section_path` is the heading trail, for example "Limits > Rate limits".
- Text before the first heading becomes "(intro)".
- Sections whose body is empty (a heading directly followed by a sub-heading) are skipped.
- Duplicate paths within a file get a " #2", " #3" suffix.
- Sections longer than `max_words` are split on paragraph boundaries ("[part N]"); fenced code
  blocks are never split.
- YAML front matter is dropped.
- The content hash ignores whitespace differences, so reformatting is not a new version.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from markdown_it import MarkdownIt

INTRO_PATH = "(intro)"
DEFAULT_MAX_WORDS = 300

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_md = MarkdownIt("commonmark")


@dataclass(frozen=True)
class Section:
    section_path: str
    text: str
    content_hash: str


def normalise(text: str) -> str:
    return " ".join(text.split())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    return len(text.split())


def _headings(text: str) -> list[tuple[int, int, int, str]]:
    """Top-level headings as (start_line, end_line, level, title)."""
    tokens = _md.parse(text)
    found = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.level == 0 and tok.map:
            title = tokens[i + 1].content.strip()
            found.append((tok.map[0], tok.map[1], int(tok.tag[1]), title))
    return found


def _blocks(lines: list[str]) -> list[str]:
    """Group lines into blank-line separated blocks, keeping fenced code intact."""
    blocks: list[list[str]] = []
    current: list[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks]


def _split(text: str, max_words: int) -> list[str]:
    if _word_count(text) <= max_words:
        return [text]
    parts: list[list[str]] = []
    current: list[str] = []
    count = 0
    for block in _blocks(text.split("\n")):
        words = _word_count(block)
        if current and count + words > max_words:
            parts.append(current)
            current, count = [], 0
        current.append(block)
        count += words
    if current:
        parts.append(current)
    return ["\n\n".join(p) for p in parts]


def parse_sections(markdown: str, max_words: int = DEFAULT_MAX_WORDS) -> list[Section]:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER.sub("", text, count=1)
    lines = text.split("\n")
    heads = _headings(text)

    # (path, start_line, end_line, body_start_line)
    segments: list[tuple[str, int, int, int]] = []
    first = heads[0][0] if heads else len(lines)
    if first > 0:
        segments.append((INTRO_PATH, 0, first, 0))

    stack: list[tuple[int, str]] = []
    for idx, (start, head_end, level, title) in enumerate(heads):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        segments.append((" > ".join(t for _, t in stack), start, end, head_end))

    sections: list[Section] = []
    seen: dict[str, int] = {}
    for path, start, end, body_start in segments:
        if not "".join(lines[body_start:end]).strip():
            continue  # nothing but a heading (or blank intro)
        seen[path] = seen.get(path, 0) + 1
        unique_path = path if seen[path] == 1 else f"{path} #{seen[path]}"
        body = "\n".join(lines[start:end]).strip()
        parts = _split(body, max_words)
        for n, part in enumerate(parts, start=1):
            part_path = unique_path if len(parts) == 1 else f"{unique_path} [part {n}]"
            sections.append(Section(part_path, part, content_hash(part)))
    return sections
