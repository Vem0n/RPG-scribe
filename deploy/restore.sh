#!/bin/sh
#
# Restore RPG Scribe database from a backup file.
#
# Usage:
#   ./deploy/restore.sh backups/rpgscribe_20260410.sql
#
set -e

if [ -z "$1" ]; then
  echo "Usage: ./deploy/restore.sh <backup_file.sql>"
  echo ""
  echo "Available backups:"
  ls -lh backups/*.sql 2>/dev/null || echo "  No backups found in backups/"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "[ERROR] File not found: $BACKUP_FILE"
  exit 1
fi

echo "[RESTORE] Restoring from $BACKUP_FILE..."
echo "[RESTORE] This will overwrite all existing data. Press Ctrl+C to cancel."
sleep 3

docker compose exec -T db psql -U rpgscribe -d rpgscribe < "$BACKUP_FILE"

echo "[RESTORE] Done. Restart the server to pick up changes:"
echo "  docker compose restart server"
