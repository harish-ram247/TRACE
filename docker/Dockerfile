# One image for every service (api, worker, ui); docker-compose.prod.yml picks the command.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_CACHE_DIR=/srv/data/models \
    LLM_CACHE_DIR=/srv/data/llm_cache

# git: the ingest worker reads repository history
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
COPY ui ./ui
RUN pip install --upgrade pip && pip install ".[ui]"

COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
# Streamlit theme and settings for the demo UI (read from the working directory)
COPY .streamlit ./.streamlit

# Run as an unprivileged user; /srv/data holds model and LLM caches (a volume in production).
RUN useradd --create-home --uid 10001 trace && mkdir -p /srv/data && chown -R trace /srv/data
USER trace

EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
