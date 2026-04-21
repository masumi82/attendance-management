#!/usr/bin/env sh
set -eu

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Ensuring initial admin..."
python -m app.seeds || true

echo "[entrypoint] Starting uvicorn..."
# Trust X-Forwarded-* only from known internal networks (nginx in the
# same compose network). Do NOT set to "*" in production.
FORWARDED_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8}"

exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips="${FORWARDED_IPS}"
