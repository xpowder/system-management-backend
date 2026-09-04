#!/bin/sh
set -e

if [ -z "$PORT" ]; then
  echo "ERROR: PORT is not set. Railway injects PORT. Delete any custom PORT variable." >&2
  exit 1
fi

echo "Starting homezup.wsgi:application on 0.0.0.0:$PORT"
python manage.py migrate --noinput
echo "Migrations done. Starting Gunicorn."
exec python -m gunicorn homezup.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --access-logfile - --error-logfile -
