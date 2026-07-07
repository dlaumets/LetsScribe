#!/usr/bin/env bash
# Download Whisper weights into models-cache (run on VPS after deploy).
set -euo pipefail

APP_DIR="${APP_DIR:-}"
if [ -z "$APP_DIR" ]; then
  if [ -d /opt/letsscribe ]; then
    APP_DIR=/opt/letsscribe
  elif [ -d /opt/letstranscriber ]; then
    APP_DIR=/opt/letstranscriber
  else
    APP_DIR=/opt/letsscribe
  fi
fi
cd "$APP_DIR"

PRESETS="${1:-quality}"
echo "==> Preloading preset(s): ${PRESETS}"

docker compose exec -T api python - "$PRESETS" <<'PY'
import sys
from faster_whisper import WhisperModel
from src.core.presets import PRESETS

requested = [p.strip() for p in sys.argv[1].split(",") if p.strip()]
for preset_id in requested:
    preset = PRESETS[preset_id]
    print(f"Loading {preset_id} ({preset.model})...", flush=True)
    WhisperModel(
        preset.model,
        device="cpu",
        compute_type=preset.compute_type,
    )
    print(f"OK: {preset_id}", flush=True)
PY

echo "==> Models cached under ${APP_DIR}/models-cache"
