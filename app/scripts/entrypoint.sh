#!/usr/bin/env bash
set -e

echo "[entrypoint] Running migrations..."
alembic upgrade head

echo "[entrypoint] Starting app..."
exec "$@"
