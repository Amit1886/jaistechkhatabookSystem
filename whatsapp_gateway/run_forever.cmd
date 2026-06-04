@echo off
setlocal
cd /d "%~dp0"

set "LOG=%~dp0gateway_supervisor.log"

echo WhatsApp Gateway supervisor (auto-restart)
echo Working dir: %CD%
echo Log file: %LOG%
echo.

:loop
echo [%DATE% %TIME%] Starting gateway...
echo [%DATE% %TIME%] Starting gateway...>> "%LOG%"
node src\server.js >> "%LOG%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%DATE% %TIME%] Gateway exited (code=%EXIT_CODE%). Restarting in 5 seconds...
echo [%DATE% %TIME%] Gateway exited (code=%EXIT_CODE%). Restarting...>> "%LOG%"
timeout /t 5 >nul
goto loop
