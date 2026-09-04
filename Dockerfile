FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_LISTEN=0.0.0.0:8000

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

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec python manage.py run_production"]
