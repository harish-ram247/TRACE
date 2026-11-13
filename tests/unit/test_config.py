from app.core.config import Settings


def test_sync_and_psycopg_urls_are_derived_from_async_url():
    s = Settings(database_url="postgresql+asyncpg://u:p@host:5432/db")
    assert s.sync_database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert s.psycopg_dsn == "postgresql://u:p@host:5432/db"
