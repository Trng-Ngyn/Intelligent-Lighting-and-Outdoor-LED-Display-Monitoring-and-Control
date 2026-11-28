#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
test -f .staging/compose.env || { echo "Run bootstrap.py first"; exit 1; }
docker version >/dev/null
docker compose version
test "$(uname -s)" = Linux || { echo "Use the Linux VPS or WSL2"; exit 1; }
docker compose --env-file .staging/compose.env -f docker-compose.staging.yml config --quiet
docker compose --env-file .staging/compose.env -f docker-compose.staging.yml up -d --build --wait --wait-timeout 300
docker compose --env-file .staging/compose.env -f docker-compose.staging.yml ps
echo "Console https://<STAGING_HOST>/ | MQTT mTLS :8883"
echo "Admin ports bind to 127.0.0.1. Use SSH tunnels for Grafana/Portainer."
