@echo off
echo Starting Django server...
cd /d "%~dp0"
rem Local run defaults (avoid HTTPS redirect + enable debug).
set DEBUG=True
set SECURE_SSL_REDIRECT=False
set "DESKTOP_MODE=False"
set "SQLITE_PATH=%~dp0db.sqlite3"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do (
  echo Port 8000 is already in use (PID=%%a). Stop the running server, then try again.
  pause
  exit /b 1
)
echo Applying migrations...
.\venv\Scripts\python.exe manage.py migrate --noinput
if %errorlevel% neq 0 (
  echo Migrations failed. Fix the error and try again.
  pause
  exit /b 1
)
start cmd /k ".\venv\Scripts\python.exe manage.py runserver --noreload 8000"
timeout /t 3 > nul
start chrome http://127.0.0.1:8000
