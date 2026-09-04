@echo off
cd /d "%~dp0"
if not exist venv\Scripts\activate.bat (
  echo Create the Python environment first: python -m venv venv
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python manage.py migrate --noinput
python manage.py check_delivery
echo.
echo Gym API: http://127.0.0.1:8000
echo If the frontend is built, the gym app opens at that same address.
echo Otherwise start the frontend with start-frontend.bat
echo.
python manage.py runserver 127.0.0.1:8000
pause
