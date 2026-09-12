# ===========================================================================
# Django backend image.
#
# The same image runs both the gunicorn HTTP workers and the daphne WebSocket
# worker -- only the command differs (see docker-compose.yml).
#
# Two stages:
#   builder  has the C compiler and dev headers, and installs every dependency
#            into a virtualenv at /opt/venv
#   runtime  is a clean slim image that copies that virtualenv in
#
# The point is that the compiler never ships to production. It keeps the final
# image several hundred MB smaller and removes build tooling an attacker could
# use, while still guaranteeing that a package with no prebuilt wheel (this
# project has a few, e.g. py-ubjson) can be compiled at build time.
# ===========================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
# Django 6.0 requires Python 3.12 or newer.
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential -> gcc and friends, for packages without a prebuilt wheel
# libpq-dev       -> PostgreSQL headers
# libffi/libssl   -> needed by cryptography and pyOpenSSL if they compile
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# A virtualenv is used purely so the whole dependency tree sits in one
# directory that can be copied to the next stage in a single COPY.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements are copied and installed BEFORE the source code, so Docker
# reuses this cached layer on every deploy where dependencies did not change.
# A code-only deploy then rebuilds in seconds instead of minutes.
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# PYTHONDONTWRITEBYTECODE: no .pyc clutter inside the container.
# PYTHONUNBUFFERED: print() and logging reach `docker compose logs`
#   immediately instead of sitting in a buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# ffmpeg -> moviepy needs the binary (vehicles/validators.py reads reel length)
# libpq5 -> PostgreSQL client library used by psycopg2 at runtime
# curl   -> the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# The compiled dependency tree, without the compiler that produced it.
COPY --from=builder /opt/venv /opt/venv

# Run as a non-root user. If the app is ever compromised, the attacker lands
# as an unprivileged user rather than root inside the container.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --chown=appuser:appuser . .

# These two directories become Docker volumes at runtime. Creating them here
# owned by appuser makes the named volumes inherit that ownership on first
# start; otherwise the container could not write uploads into /app/media.
RUN mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app/media /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Overridden in docker-compose.yml for the WebSocket worker.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
