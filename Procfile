web: python manage.py migrate --noinput && python -m gunicorn homezup.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --access-logfile - --error-logfile -
