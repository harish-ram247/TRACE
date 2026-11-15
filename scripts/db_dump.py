"""Dump the local TRACE database to a file, for restoring on the server.

Usage: python -m scripts.db_dump [--out data/trace.dump]

Re-ingesting and re-embedding the corpus on a small server takes a long time; restoring a dump
takes seconds and guarantees the server has exactly the evaluated data. Uses the pg_dump bundled
with pgserver if present, else the one on PATH. Restore steps are in docs/deploy.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings


def pg_dump_path() -> str:
    try:
        from pgserver._commands import POSTGRES_BIN_PATH

        exe = Path(POSTGRES_BIN_PATH) / ("pg_dump.exe" if sys.platform == "win32" else "pg_dump")
        if exe.exists():
            return str(exe)
    except ImportError:
        pass
    found = shutil.which("pg_dump")
    if not found:
        raise SystemExit("pg_dump not found (install PostgreSQL client tools or pgserver)")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/trace.dump"))
    args = parser.parse_args(argv)
    url = urlparse(get_settings().psycopg_dsn)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        pg_dump_path(), "--format=custom", "--no-owner", "--no-privileges",
        "-h", url.hostname or "localhost", "-p", str(url.port or 5432),
        "-U", url.username or "trace", "-d", url.path.lstrip("/"),
        "-f", str(args.out),
    ]  # fmt: skip
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    subprocess.run(cmd, check=True, env=env)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
