#!/usr/bin/env bash
# Install standalone server monitor to /opt/server-monitor
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/server-monitor}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing server monitor to ${APP_DIR}..."
mkdir -p "$APP_DIR"
cp "$SRC_DIR/monitor_bot.py" "$SRC_DIR/collectors.py" "$SRC_DIR/metrics.py" \
   "$SRC_DIR/charts.py" "$SRC_DIR/requirements.txt" "$APP_DIR/"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$SRC_DIR/.env.example" "$APP_DIR/.env"
  echo "!!! Edit ${APP_DIR}/.env — set MONITOR_BOT_TOKEN and MONITOR_ALLOWED_IDS"
else
  echo "    Keeping existing ${APP_DIR}/.env"
fi

sed -i 's/\r$//' "$APP_DIR/.env" 2>/dev/null || true

if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

cp "$SRC_DIR/server-monitor.service" /etc/systemd/system/server-monitor.service
systemctl daemon-reload
systemctl enable server-monitor
systemctl restart server-monitor

echo "==> Done. Service: server-monitor (@LetsTracker_bot)"
systemctl is-active server-monitor
