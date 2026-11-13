"""Synchronous psycopg connection pool for request handlers (retrieval uses psycopg + pgvector)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

import psycopg
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


@lru_cache
def get_pool() -> ConnectionPool:
    return ConnectionPool(
        get_settings().psycopg_dsn,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True},
        open=True,
    )


def get_conn() -> Iterator[psycopg.Connection]:
    with get_pool().connection() as conn:
        yield conn
