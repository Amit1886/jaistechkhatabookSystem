@echo off
echo Starting WhatsApp Gateway (QR / WPPConnect)...
cd /d "%~dp0"

if not exist "whatsapp_gateway\.env" (
  echo Creating whatsapp_gateway\.env from whatsapp_gateway\.env.example ...
  copy /Y "whatsapp_gateway\.env.example" "whatsapp_gateway\.env" >nul
)

echo Opening a new terminal window for the gateway (auto-restart enabled)...
echo If port 3100 is already in use, stop the other process first.
start "WhatsApp Gateway" cmd /k "cd /d \"%~dp0whatsapp_gateway\" && run_forever.cmd"
echo Gateway UI: http://127.0.0.1:3100
