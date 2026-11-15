from fastapi import FastAPI

from app.api import admin, ask, corpus, errors, health
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging(get_settings().log_level)

app = FastAPI(
    title="TRACE",
    description="Temporal Retrieval with Attributed Claim Evidence",
    version="0.1.0",
)
errors.install(app)
app.include_router(health.router)
app.include_router(ask.router)
app.include_router(corpus.router)
app.include_router(admin.router)
