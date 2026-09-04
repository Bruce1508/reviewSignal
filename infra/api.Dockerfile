FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONPATH=/app/apps/api:/app/workers \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY apps/api ./apps/api
COPY workers ./workers
COPY migrations ./migrations
COPY alembic.ini ./

EXPOSE 8000
CMD ["uvicorn", "reviewsignal_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
