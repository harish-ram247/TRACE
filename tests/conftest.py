import psycopg
import pytest

from app.core.config import get_settings


@pytest.fixture
def pg():
    """A psycopg connection inside a transaction that is always rolled back.

    Skips the test if PostgreSQL is not reachable, so unit tests still run anywhere.
    """
    try:
        conn = psycopg.connect(get_settings().psycopg_dsn, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
