#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint for the Django image.
#
# Runs before every start of the `web` and `ws` containers. It waits for the
# database to actually accept connections, then (only in the container that
# asks for it) applies migrations and collects static files, and finally hands
# control to whatever command docker-compose passed in.
# ---------------------------------------------------------------------------
set -euo pipefail

# `set -e` above means any failing command aborts the container start, which is
# what we want: better to crash loudly than to serve a half-migrated database.

echo "[entrypoint] waiting for the database..."

# Compose's `depends_on: condition: service_healthy` already waits for Postgres,
# but this second check costs nothing and protects against the database being
# restarted underneath us.
python <<'PYWAIT'
import os, sys, time, urllib.parse

url = os.environ.get("DATABASE_URL", "")
parsed = urllib.parse.urlparse(url)
if parsed.scheme.startswith("postgres"):
    import socket
    host = parsed.hostname or "db"
    port = parsed.port or 5432
    for attempt in range(60):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[entrypoint] database reachable at {host}:{port}")
                sys.exit(0)
        except OSError:
            time.sleep(1)
    print("[entrypoint] database never became reachable", file=sys.stderr)
    sys.exit(1)
else:
    print("[entrypoint] non-postgres DATABASE_URL, skipping wait")
PYWAIT

# Only ONE container may run migrations, otherwise two workers starting at the
# same moment race each other on the same tables. docker-compose.yml sets
# RUN_MIGRATIONS=true on `web` only.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] applying database migrations..."
    python manage.py migrate --noinput

    echo "[entrypoint] collecting static files..."
    # Copies admin + django-unfold CSS/JS into /app/staticfiles, which is a
    # shared volume that nginx serves directly.
    python manage.py collectstatic --noinput --clear
fi

echo "[entrypoint] starting: $*"

# `exec` replaces this shell with the real process, so it becomes PID 1 and
# receives Docker's stop signals directly (clean shutdowns, no 10s SIGKILL wait).
exec "$@"
