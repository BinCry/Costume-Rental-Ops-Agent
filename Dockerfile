# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/

WORKDIR /app

# Install locked production dependencies before copying the source so this
# expensive layer remains cached when only application code changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH \
    HOST=0.0.0.0 \
    PORT=8001 \
    KNOWLEDGE_MODEL_CACHE_DIR=/app/.cache/huggingface

# PyTorch CPU wheels require libgomp at runtime. Coolify's URL healthcheck
# probes containers with curl (falling back to wget), so keep curl available
# in the production image as well.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes curl libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

WORKDIR /app

COPY --from=build --chown=app:app /app/.venv ./.venv
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app sql ./sql
COPY --chown=app:app knowledge-base ./knowledge-base
COPY --chown=app:app tests/retrieval/knowledge-base-queries.jsonl ./tests/retrieval/knowledge-base-queries.jsonl

RUN mkdir -p /app/.cache/huggingface && chown -R app:app /app/.cache

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8001') + '/health', timeout=4)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host \"${HOST:-0.0.0.0}\" --port \"${PORT:-8001}\""]
