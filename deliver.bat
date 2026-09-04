@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
cd frontend
call npm run build
cd ..
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check_delivery
python manage.py run_production
pause
