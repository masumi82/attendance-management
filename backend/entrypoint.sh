#!/usr/bin/env sh
set -eu

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Ensuring initial admin..."
python -m app.seeds || true

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips="*"
