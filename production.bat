@echo off
cd /d "%~dp0"
if not exist venv\Scripts\activate.bat (
  echo Create the Python environment first: python -m venv venv
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py check_delivery
echo.
echo Production server. Stop with Ctrl+C.
echo.
python manage.py run_production
pause
