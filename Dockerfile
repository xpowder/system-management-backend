FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY manage.py .
COPY homezup ./homezup
COPY core ./core
COPY users ./users
COPY bookings ./bookings
COPY fitness ./fitness

RUN mkdir -p logs media staticfiles \
    && DJANGO_SECRET_KEY=build-time-collectstatic-key-min-32-chars \
       DJANGO_DEBUG=False \
       DJANGO_HTTPS=False \
       DJANGO_ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput

# LF-only scripts so a Windows checkout cannot break the Linux container.
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'if [ -z "$PORT" ]; then' \
    '  echo "ERROR: PORT is not set. Railway injects PORT. Delete any custom PORT variable." >&2' \
    '  exit 1' \
    'fi' \
    'echo "Starting homezup.wsgi:application on 0.0.0.0:$PORT"' \
    'python manage.py migrate --noinput' \
    'echo "Migrations done. Starting Gunicorn."' \
    'exec python manage.py run_production' \
    > /app/start.sh \
    && printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    'if [ ! -t 0 ]; then' \
    '  echo "ERROR: createsuperuser is not the web start command." >&2' \
    '  echo "Create a user from Railway Shell: python manage.py createsuperuser" >&2' \
    '  exit 1' \
    'fi' \
    'exec python manage.py createsuperuser "$@"' \
    > /app/create-superuser.sh \
    && chmod +x /app/start.sh /app/create-superuser.sh

CMD ["/bin/sh", "/app/start.sh"]
