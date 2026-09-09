@echo off
echo ====================================
echo  JaisTech Billentra - DEV Server
echo  Port: 8080  (autoreload ON)
echo ====================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found! Run: python -m venv .venv
  pause
  exit /b 1
)

set DEBUG=True
set SECURE_SSL_REDIRECT=False
set DESKTOP_MODE=False
set BASE_URL=http://127.0.0.1:8080
set CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8080,http://localhost:8080

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080" ^| findstr LISTENING') do (
  echo Port 8080 is already in use (PID=%%a). Stop the running server, then try again.
  pause
  exit /b 1
)

echo Applying migrations...
.\.venv\Scripts\python.exe manage.py migrate --noinput
if %errorlevel% neq 0 (
  echo Migrations failed.
  pause
  exit /b 1
)

start cmd /k ".\.venv\Scripts\python.exe manage.py runserver 8080"
timeout /t 3 >nul
start chrome http://127.0.0.1:8080
