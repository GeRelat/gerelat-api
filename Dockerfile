FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    DJANGO_ENV=prod \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONHASHSEED=random

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN uv run manage.py collectstatic --noinput

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/').read()"

CMD ["sh", "-c", "uv run manage.py migrate && uv run granian config.asgi:application --interface asgi --host 0.0.0.0 --port 8000"]