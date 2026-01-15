#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${DB_HOST:-}" ]]; then
  echo "Waiting for database at ${DB_HOST}:${DB_PORT:-5432}..."
  python - <<'PY'
import os
import socket
import sys
import time

host = os.getenv("DB_HOST")
port = int(os.getenv("DB_PORT", "5432"))

timeout = 60
start = time.time()
while True:
    try:
        with socket.create_connection((host, port), timeout=5):
            print("Database is reachable.")
            break
    except OSError as exc:
        if time.time() - start > timeout:
            print(f"Database not reachable after {timeout}s: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

if [[ "${DJANGO_COLLECTSTATIC:-0}" == "1" ]]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

echo "Starting server..."
exec "$@"
