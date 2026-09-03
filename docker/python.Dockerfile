FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --extra viirs

COPY dashboard ./dashboard
COPY config ./config

EXPOSE 8000
