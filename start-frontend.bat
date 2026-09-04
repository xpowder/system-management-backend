@echo off
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Installing frontend packages...
  call npm install
)
echo Gym app: http://localhost:5173
call npm run dev
pause
