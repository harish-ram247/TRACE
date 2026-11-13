import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.db import engine

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db() -> dict[str, str]:
    """Readiness: the database answers and the required extensions exist."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'btree_gist')")
            )
            found = {row[0] for row in result}
    except Exception as exc:
        log.warning("database health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    missing = {"vector", "btree_gist"} - found
    if missing:
        raise HTTPException(status_code=503, detail=f"missing extensions: {sorted(missing)}")
    return {"status": "ok"}
