$ErrorActionPreference = "Stop"

$taskName = "JaisTech WhatsApp Gateway"

Write-Host "Removing Scheduled Task: $taskName"

& schtasks.exe /Delete /TN $taskName /F | Out-Host

Write-Host "Done."
