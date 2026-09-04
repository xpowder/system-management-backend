#!/bin/sh
set -e

echo "Starting Homezup Django backend"

if [ -z "$PORT" ]; then
  echo "ERROR: PORT is not set. Railway injects PORT. Delete any custom PORT variable." >&2
  exit 1
fi

echo "PORT detected"
echo "Starting homezup.wsgi:application on 0.0.0.0:$PORT"
echo "Running migrations"
python manage.py migrate --noinput
echo "Migrations done. Starting Gunicorn."
exec python -m gunicorn homezup.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --error-logfile - \
  --log-level info
