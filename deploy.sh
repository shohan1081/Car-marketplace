#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command redeploy, to be run on the EC2 instance from the repo directory.
#
#   ./deploy.sh
#
# It pulls the latest code, rebuilds only what changed, restarts the stack and
# shows you the result. Migrations and collectstatic run automatically inside
# the `web` container's entrypoint, so there is nothing else to remember.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

echo "==> 1/5  Checking for a .env file"
if [ ! -f .env ]; then
    echo "ERROR: .env is missing. Copy .env.production.example to .env and fill it in." >&2
    exit 1
fi

echo "==> 2/5  Pulling the latest code from GitLab"
# --ff-only refuses to create a merge commit. If this fails, the server has
# local edits that must be dealt with by hand -- which is exactly when you
# want a deploy to stop rather than silently merge.
git pull --ff-only

echo "==> 3/5  Rebuilding images"
# Only layers whose inputs changed are rebuilt, so a code-only change is fast.
docker compose build

echo "==> 4/5  Restarting the stack"
# --remove-orphans cleans up containers for services you deleted from the
# compose file. Containers whose config did not change are left running.
docker compose up -d --remove-orphans

echo "==> 5/5  Removing images left behind by previous builds"
# Untagged old image layers otherwise fill the EC2 disk over time.
docker image prune -f

echo
docker compose ps
echo
echo "Deploy finished. Follow the logs with:  docker compose logs -f web"
