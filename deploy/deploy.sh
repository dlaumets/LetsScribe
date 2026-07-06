#!/usr/bin/env bash
# Pull latest code and rebuild containers
set -euo pipefail

APP_DIR="${APP_DIR:-}"
if [ -z "$APP_DIR" ]; then
  if [ -d /opt/letsscribe ]; then
    APP_DIR=/opt/letsscribe
  elif [ -d /opt/letstranscriber ]; then
    APP_DIR=/opt/letstranscriber
    echo "==> Using legacy ${APP_DIR} — run deploy/migrate-to-letsscribe.sh when ready"
  else
    APP_DIR=/opt/letsscribe
  fi
fi
cd "$APP_DIR"

echo "==> Pulling latest..."
git fetch origin main
git reset --hard origin/main

echo "==> Building and starting services..."
docker compose --profile bot --profile prod pull --ignore-buildable 2>/dev/null || true
docker compose --profile bot --profile prod up -d --build --remove-orphans

echo "==> Cleaning old images..."
docker image prune -f

echo "==> Status:"
docker compose ps

echo "==> Deploy done at $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
