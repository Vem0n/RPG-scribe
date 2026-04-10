#!/bin/sh
#
# Backup RPG Scribe database to a timestamped SQL file.
#
# Usage:
#   ./deploy/backup.sh                    # saves to backups/rpgscribe_<timestamp>.sql
#   ./deploy/backup.sh my_backup.sql      # saves to my_backup.sql
#
set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="${1:-$BACKUP_DIR/rpgscribe_$TIMESTAMP.sql}"

mkdir -p "$(dirname "$OUTPUT")"

echo "[BACKUP] Dumping database..."
docker compose exec -T db pg_dump -U rpgscribe --clean --if-exists rpgscribe > "$OUTPUT"

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "[BACKUP] Saved to $OUTPUT ($SIZE)"
