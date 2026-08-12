FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    DJANGO_ENV=prod \
    DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONHASHSEED=random

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN uv run manage.py collectstatic --noinput

RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "uv run granian config.asgi:application --interface asgi --host 0.0.0.0 --port 8000"]
