$ErrorActionPreference = "Stop"

$taskName = "JaisTech WhatsApp Gateway"
$root = $PSScriptRoot
$runner = Join-Path $root "whatsapp_gateway\\run_forever.cmd"

if (-not (Test-Path $runner)) {
  throw "Missing: $runner"
}

Write-Host "Installing Scheduled Task: $taskName"
Write-Host "Runner: $runner"

$tr = ('"{0}"' -f $runner)
$args = @(
  "/Create",
  "/SC", "ONLOGON",
  "/TN", $taskName,
  "/TR", $tr,
  "/RL", "LIMITED",
  "/F"
)

& schtasks.exe @args | Out-Host

Write-Host ""
Write-Host "Done. The gateway will auto-start on next Windows login."
Write-Host "To remove: run uninstall_whatsapp_gateway_autostart.ps1"
