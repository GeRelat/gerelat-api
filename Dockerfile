FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    DJANGO_ENV=prod \
    DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONHASHSEED=random

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

RUN uv run manage.py collectstatic --noinput

FROM builder AS dev

ENV DJANGO_ENV=dev

RUN uv sync --frozen

CMD ["uv", "run", "manage.py", "runserver", "0.0.0.0:8000"]

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=prod \
    DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONHASHSEED=random \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder --chown=app:app /app /app

USER app

EXPOSE 8000

CMD ["granian", "config.asgi:application", "--interface", "asginl", "--host", "0.0.0.0", "--port", "8000"]
