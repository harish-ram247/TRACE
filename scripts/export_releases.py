"""Export Vite release dates from the corpus clone's git tags to a JSON file.

For every vMAJOR.MINOR.0 release it records the release date and the date of the first
prerelease tag (vMAJOR.MINOR.0-alpha/beta/rc). The docs on the main branch usually start
describing a new version during its prereleases, so "before Vite N" means "before the first
prerelease of N".

Usage: python -m scripts.export_releases [--repo data/corpus/vite]

The output (app/temporal/vite_releases.json) is committed, so the API needs no git clone at
runtime. Dates are each tag's creator date (tagger date for annotated tags, else commit date).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OUT = Path("app/temporal/vite_releases.json")
_TAG = re.compile(r"^v(\d+)\.(\d+)\.0(-[0-9A-Za-z.]+)?$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="data/corpus/vite")
    args = parser.parse_args(argv)
    out = subprocess.run(
        [
            "git",
            "-C",
            args.repo,
            "for-each-ref",
            "--format=%(refname:short) %(creatordate:iso-strict)",
            "refs/tags/v*",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    final: dict[str, str] = {}
    first_pre: dict[str, str] = {}
    for line in out.splitlines():
        tag, date = line.split(" ", 1)
        if not (m := _TAG.match(tag)):
            continue
        version = f"{m.group(1)}.{m.group(2)}"
        if m.group(3):  # prerelease
            if version not in first_pre or date < first_pre[version]:
                first_pre[version] = date
        else:
            final[version] = date
    releases = {v: {"release": final[v], "first_prerelease": first_pre.get(v)} for v in final}
    ordered = dict(sorted(releases.items(), key=lambda kv: tuple(map(int, kv[0].split(".")))))
    OUT.write_text(
        json.dumps(
            {"source": "https://github.com/vitejs/vite tags vX.Y.0", "releases": ordered}, indent=1
        )
        + "\n",
        "utf-8",
    )
    print(f"wrote {len(ordered)} releases to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
