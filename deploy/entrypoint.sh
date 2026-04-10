#!/bin/sh
set -e

echo "============================================"
echo "  RPG Scribe Server"
echo "============================================"
echo ""

# Check required env vars
if [ -z "$DATABASE_URL" ]; then
  echo "[FATAL] DATABASE_URL is not set"
  exit 1
fi
echo "[OK] DATABASE_URL configured"

if [ -z "$API_KEY" ]; then
  echo "[FATAL] API_KEY is not set"
  exit 1
fi
echo "[OK] API_KEY configured"

echo "[OK] Port: ${PORT:-8080}"
echo "[OK] Environment: ${ENV:-production}"
echo ""

# Auto-seed if seed data exists and SEED_ON_START is not disabled
SEED_DIR="${SEED_DATA_DIR:-/data/seed-data}"
if [ "$SEED_ON_START" != "false" ] && [ -d "$SEED_DIR" ] && [ "$(ls -A "$SEED_DIR" 2>/dev/null)" ]; then
  echo "[SEED] Found seed data in $SEED_DIR"
  if rpg-scribe-seed --data-dir="$SEED_DIR" 2>&1; then
    echo "[SEED] Seeding complete"
  else
    echo "[WARN] Seeding failed — server will start anyway"
  fi
  echo ""
else
  echo "[SEED] Skipped (no seed data or SEED_ON_START=false)"
  echo ""
fi

echo "[START] Launching RPG Scribe server..."
echo ""
exec rpg-scribe "$@"
