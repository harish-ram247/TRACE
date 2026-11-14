"""Run PostgreSQL + pgvector locally without Docker, using the binaries bundled in `pgserver`.

Usage: python -m scripts.local_db start | stop | status

Data lives in data/pgdata (git-ignored). The server listens on 127.0.0.1:5433 with a `trace`
role and database, the same address as the Docker Compose setup, so .env does not change.
This is a fallback for machines where Docker Desktop does not work. Differences from the Docker
image (pgvector/pgvector:pg16): pgvector 0.6 instead of 0.8 (no iterative index scans) and no
btree_gist extension (the schema does not need it; see migration 0004).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PGDATA = Path("data/pgdata").resolve()
LOG = Path("data/pgdata.log").resolve()
PORT = 5433
ROLE = DB = "trace"


def _bin(name: str) -> str:
    from pgserver._commands import POSTGRES_BIN_PATH

    exe = Path(POSTGRES_BIN_PATH) / (name + (".exe" if sys.platform == "win32" else ""))
    return str(exe)


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check)


def _psql(sql: str, db: str = "postgres") -> str:
    out = _run(_bin("psql"), "-h", "127.0.0.1", "-p", str(PORT), "-U", "postgres", "-d", db,
               "-tAc", sql)  # fmt: skip
    return out.stdout.strip()


def status() -> bool:
    return _run(_bin("pg_ctl"), "-D", str(PGDATA), "status", check=False).returncode == 0


def start() -> None:
    if not (PGDATA / "PG_VERSION").exists():
        PGDATA.parent.mkdir(parents=True, exist_ok=True)
        _run(_bin("initdb"), "-D", str(PGDATA), "-U", "postgres", "--auth=trust", "-E", "UTF8")
        print(f"initialised {PGDATA}")
    if status():
        print("already running")
    else:
        # No captured pipes: on Windows the server inherits them and the call would never return.
        subprocess.run(
            [_bin("pg_ctl"), "-D", str(PGDATA), "-l", str(LOG), "-w",
             "-o", f"-p {PORT} -h localhost", "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            check=True,
        )  # fmt: skip
        print(f"started on localhost:{PORT} (log: {LOG})")
    if _psql(f"SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}'") != "1":
        _psql(f"CREATE ROLE {ROLE} LOGIN SUPERUSER PASSWORD '{ROLE}'")
    if _psql(f"SELECT 1 FROM pg_database WHERE datname = '{DB}'") != "1":
        _psql(f"CREATE DATABASE {DB} OWNER {ROLE}")
    print(f"ready: postgresql://{ROLE}:{ROLE}@localhost:{PORT}/{DB}")


def stop() -> None:
    if status():
        _run(_bin("pg_ctl"), "-D", str(PGDATA), "-w", "stop")
        print("stopped")
    else:
        print("not running")


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "status"
    if command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "status":
        print("running" if status() else "not running")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
