"""Precompute the web demo's example answers into web/examples.json.

The page shows these instantly (no API call, no LLM wait), including the evidence view: for every
cited source the section's full version history is stored too. Re-run after changing the corpus,
prompts or the example list. Needs the API running:

    python -m scripts.build_web_examples            # TRACE_API_URL defaults to http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

API = os.environ.get("TRACE_API_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "web" / "examples.json"

# (short label for the picker, question, date or None to read the date from the question). Dates are
# chosen where the docs changed, so the then-vs-now difference is visible.
EXAMPLES: list[tuple[str, str, str | None]] = [
    ("Preview server port", "What port does vite preview use by default?", "2022-01-01"),
    ("Dev server port", "What port does the Vite dev server use by default?", "2022-01-01"),
    ("Default build target", "What is the default value of build.target?", "2022-03-01"),
    ("Required Node.js version", "Which Node.js version does Vite require?", "2022-06-01"),
    ("Dev server host", "Which IP address does the dev server listen on by default?", "2022-01-01"),
    (
        "Default minifier",
        "Which minifier does Vite use by default for production builds?",
        "2021-03-01",
    ),
]


def ask(client: httpx.Client, question: str, variant: str, as_of: str | None) -> dict:
    body: dict = {"question": question, "variant": variant}
    if as_of:
        body["as_of"] = f"{as_of}T23:59:59+00:00"
    r = client.post(f"{API}/ask", json=body, timeout=300)
    r.raise_for_status()
    return r.json()


def cited(body: dict) -> list[dict]:
    labels = set(body.get("cited_labels") or [])
    return [s for s in body.get("sources") or [] if s["label"] in labels]


def lineage(client: httpx.Client, chunk_id: int) -> dict:
    chunk = client.get(f"{API}/chunks/{chunk_id}", timeout=30)
    chunk.raise_for_status()
    c = chunk.json()
    lin = client.get(f"{API}/lineages/{c['lineage_id']}", timeout=30)
    lin.raise_for_status()
    return {**lin.json(), "source_path": c["source_path"], "section_path": c["section_path"]}


def main() -> int:
    out = []
    with httpx.Client() as client:
        for label, question, as_of in EXAMPLES:
            print(f"- {question} (as of {as_of or 'date in question'})", flush=True)
            trace = ask(client, question, "temporal_verified", as_of)
            plain = ask(client, question, "plain", None)
            lineages = {}
            for s in cited(trace) + cited(plain):
                if str(s["chunk_id"]) not in lineages:
                    lineages[str(s["chunk_id"])] = lineage(client, s["chunk_id"])
            out.append(
                {"label": label, "question": question, "as_of": as_of, "trace": trace,
                 "plain": plain, "lineages": lineages}
            )  # fmt: skip
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(out)} examples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
