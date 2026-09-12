#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Database + media backup, to be run on the EC2 instance.
#
#   ./backup.sh
#
# Writes a compressed PostgreSQL dump and a media archive into ./backups and
# deletes anything older than 14 days. Run it from cron:
#
#   0 3 * * * cd /home/ubuntu/nory-backend && ./backup.sh >> backups/backup.log 2>&1
#
# A backup on the same EC2 instance protects you from a bad migration, not
# from losing the instance. Copy the files off the box (S3) as well.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
set -a; . ./.env; set +a   # load POSTGRES_USER / POSTGRES_DB

BACKUP_DIR="./backups"
STAMP="$(date +%Y-%m-%d_%H-%M)"
RETENTION_DAYS=14

mkdir -p "$BACKUP_DIR"

echo "==> Dumping the database"
# pg_dump runs INSIDE the db container, so no PostgreSQL client is needed on
# the host. -T disables TTY allocation, which would corrupt the piped output.
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz"

echo "==> Archiving uploaded media"
# The media volume is read through a throwaway alpine container, so this works
# even if the web container is stopped.
docker run --rm \
    -v "$(docker volume ls -q -f name=_media_data | head -n1)":/media:ro \
    -v "$(pwd)/$BACKUP_DIR":/backup \
    alpine tar czf "/backup/media_$STAMP.tar.gz" -C /media .

echo "==> Deleting backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name '*.gz' -mtime +$RETENTION_DAYS -delete

echo
ls -lh "$BACKUP_DIR" | tail -n 10
echo "Backup complete."
