from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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

origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )

# The web demo (web/): static files, same origin as the API, so it needs no CORS.
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.is_dir():
    app.mount("/demo", StaticFiles(directory=WEB_DIR, html=True), name="demo")

    @app.get("/demo", include_in_schema=False)
    def demo_slash() -> RedirectResponse:
        return RedirectResponse("/demo/")
