# --- 1. The "Base" Stage ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /retainly/backend

ENV VIRTUAL_ENV=/retainly/backend/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN useradd -m -u 1000 appuser
RUN mkdir -p /retainly/media && chown -R appuser:appuser /retainly /retainly/media

RUN apt-get update && \
    apt-get install -y libmagic1 && \
    rm -rf /var/lib/apt/lists/*

USER appuser


# --- 2. The "Development/Testing" Stage ---
FROM base AS dev

COPY --chown=appuser:appuser pyproject.toml .python-version uv.lock* ./

# FIX: Added uid=1000,gid=1000 to the cache mount
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen

RUN ipython profile create && \
    echo "c.InteractiveShellApp.extensions = ['autoreload']" >> ~/.ipython/profile_default/ipython_config.py && \
    echo "c.InteractiveShellApp.exec_lines = ['%autoreload 2']" >> ~/.ipython/profile_default/ipython_config.py

CMD ["python", "-m", "uvicorn", "app.core.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- 3. The "Production" Stage ---
FROM base AS prod

COPY --chown=appuser:appuser pyproject.toml .python-version uv.lock* ./

# FIX: Added uid=1000,gid=1000 to the cache mount here too
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen --no-dev

COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./alembic ./alembic
COPY --chown=appuser:appuser ./alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.core.main:app", "--bind", "0.0.0.0:8000"]
