# ===========================================================================
# car-video-agent -- FastAPI service that turns dealer photos into an AI video
# (fal.ai Kling + OpenAI vision) and posts the result back to Django.
#
# This container is NOT exposed to the internet. Only the Django containers
# reach it, over the private Docker network, at http://agent:8000.
# ===========================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder -- has the compiler, so any dependency without a prebuilt
# wheel still installs cleanly.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies first, so a code-only change does not re-run pip install.
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is used by the container healthcheck below.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Compose restarts the container if this keeps failing.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Two workers: one video job holds a worker's thread for minutes, so with a
# single worker a second dealer's request would queue behind it.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
