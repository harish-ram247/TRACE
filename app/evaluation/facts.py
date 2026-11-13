"""Mine fact timelines from the versioned chunks, and check answers against them.

A fact is one thing the documentation states that can change over time:
- the documented default of a config option (`- **Default:** value` lines in docs/config)
- the Node.js version Vite requires (Getting Started > Scaffolding)

Its timeline is a list of spans: (core value, valid from, valid until, where it was stated).
Gold answers come straight from the documentation text at that time; no LLM is involved.

"Core value" ignores cosmetic edits: link targets, "4kb" vs "4 KiB" notes, quote style. Only a
change of the code value itself (first backtick span) counts as a change.

Answer checking uses key tokens (numbers, quoted strings, identifiers) of the gold value and of
values valid at other times. An answer is correct if it contains every gold token and no token
that only appears in other (stale) values. Fragile cases are flagged for manual review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import psycopg

_DEFAULT = re.compile(r"\*\*Default:?\*\*:?\s*(.+)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BACKTICK = re.compile(r"`([^`]+)`")
_NODE = re.compile(
    r"Node\.js\]\([^)]*\)\s+(?:version\s+)?"
    r"((?:>=\s*)?\d+(?:\.\d+)*\+?(?:(?:,\s*|\s+or\s+|\.\s+(?=\d))(?:>=\s*)?\d+(?:\.\d+)*\+?)*)"
)


@dataclass(frozen=True)
class Segment:
    start: datetime
    end: datetime | None
    raw: str
    core: str
    source_path: str
    section_path: str
    chunk_id: int


@dataclass
class Span:
    core: str
    raw: str
    start: datetime
    end: datetime | None
    segments: list[Segment] = field(default_factory=list)

    def segment_at(self, when: datetime) -> Segment | None:
        for s in self.segments:
            if s.start <= when and (s.end is None or when < s.end):
                return s
        return None


@dataclass
class Fact:
    key: str
    kind: str  # "default" | "node_requirement"
    subject: str  # e.g. "build.minify"
    spans: list[Span]
    first_seen: datetime  # first time the subject appears at all (with or without a value)

    @property
    def changed(self) -> bool:
        return len({s.core for s in self.spans}) > 1


# ---------------------------------------------------------------------------- normalisation
def core_value(raw: str) -> str:
    text = _LINK.sub(r"\1", raw).strip()
    m = _BACKTICK.search(text)
    value = m.group(1) if m else re.split(r"[(,;]| for | unless ", text)[0]
    value = value.strip().strip(":").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return " ".join(value.split())


def _strip_zeros(version: str) -> str:
    while version.endswith(".0") and version.count(".") >= 1:
        version = version[:-2]
    return version


def key_tokens(value: str) -> list[str]:
    """Distinctive tokens of a value: quoted items, version numbers, identifiers."""
    tokens: list[str] = []
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", value)
    tokens += quoted
    rest = re.sub(r"['\"][^'\"]*['\"]", " ", value)
    for num in re.findall(r"(?<![A-Za-z_\d.])\d+(?:\.\d+)*", rest):  # not "2020" in "es2020"
        tokens.append(_strip_zeros(num))
    for word in re.findall(r"[A-Za-z_][\w.@/-]*", rest):
        if word.lower() not in {"or", "and", "for", "the"}:
            tokens.append(word)
    seen, out = set(), []
    for t in tokens:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _normalise_answer(text: str) -> str:
    return text.replace("`", " ").replace("'", " ").replace('"', " ").lower()


def contains_token(answer: str, token: str) -> bool:
    norm = _normalise_answer(answer)
    tok = token.lower()
    if re.fullmatch(r"\d+(?:\.\d+)*", tok):  # 14.18 matches "14.18", "14.18.0", "14.18+"
        pattern = rf"(?<![\w.]){re.escape(tok)}(?:\.0)*(?![\w]|\.\d)"
    else:
        pattern = rf"(?<![\w-]){re.escape(tok)}(?![\w-])"
    return re.search(pattern, norm) is not None


def check_answer(
    answer: str, gold_tokens: list[str], stale_tokens: list[str], answerable: bool = True
) -> bool:
    if not answerable:
        return answer.strip().upper().startswith("NOT_FOUND")
    if answer.strip().upper().startswith("NOT_FOUND"):
        return False
    has_gold = all(contains_token(answer, t) for t in gold_tokens)
    has_stale = any(contains_token(answer, t) for t in stale_tokens)
    return has_gold and not has_stale


# ---------------------------------------------------------------------------- mining
def _option_name(section_path: str) -> str:
    last = section_path.split(" > ")[-1]
    last = re.sub(r"\s*\[part \d+\]$", "", last)
    last = re.sub(r"\s*#\d+$", "", last)
    last = re.sub(r"\s*<[A-Za-z][^>]*>.*$", "", last)  # <Badge ...>, <NonInheritBadge />
    return last.strip().strip("`")


def _merge(segments: list[Segment]) -> list[Span]:
    spans: list[Span] = []
    for seg in sorted(segments, key=lambda s: s.start):
        last = spans[-1] if spans else None
        if last and last.core == seg.core and last.end == seg.start:
            last.end = seg.end
            last.segments.append(seg)
        else:
            spans.append(Span(seg.core, seg.raw, seg.start, seg.end, [seg]))
    return spans


def _overlapping(segments: list[Segment]) -> bool:
    ordered = sorted(segments, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if a.end is None or a.end > b.start:
            return True
    return False


def mine_facts(conn: psycopg.Connection, repo_id: str) -> list[Fact]:
    rows = conn.execute(
        """
        SELECT c.id, d.source_path, c.section_path, c.text, lower(c.valid), upper(c.valid)
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s
          AND (d.source_path LIKE 'docs/config/%%' OR d.source_path = 'docs/guide/index.md')
        ORDER BY lower(c.valid), c.id
        """,
        (repo_id,),
    ).fetchall()

    defaults: dict[str, list[Segment]] = {}
    first_seen: dict[str, datetime] = {}
    node: list[Segment] = []
    for cid, path, section, text, start, end in rows:
        if path.startswith("docs/config/"):
            option = _option_name(section)
            if "." not in option and option not in ("root", "base", "mode", "define", "plugins"):
                continue  # headings like "Server Options" are not options
            first_seen[option] = min(first_seen.get(option, start), start)
            if m := _DEFAULT.search(text):
                raw = m.group(1).strip()
                core = core_value(raw)
                if core:
                    seg = Segment(start, end, raw, core, path, section, cid)
                    defaults.setdefault(option, []).append(seg)
        elif "Scaffolding" in section and (m := _NODE.search(text)):
            raw = m.group(1).strip()
            node.append(Segment(start, end, raw, " ".join(raw.split()), path, section, cid))

    facts = []
    for option, segs in sorted(defaults.items()):
        if _overlapping(segs):
            continue  # two pages disagreeing at the same time: not a clean fact
        facts.append(Fact(f"default:{option}", "default", option, _merge(segs), first_seen[option]))
    if node and not _overlapping(node):
        facts.append(
            Fact("node_requirement", "node_requirement", "Node.js", _merge(node), node[0].start)
        )
    return facts
