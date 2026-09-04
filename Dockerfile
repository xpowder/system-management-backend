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
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh \
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
    && chmod +x /app/create-superuser.sh

# No ENTRYPOINT. Railway startCommand replaces CMD; combining both
# prepends start.sh arguments and can skip Gunicorn.
CMD ["/bin/sh", "/app/start.sh"]
