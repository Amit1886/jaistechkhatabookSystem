param(
  [switch]$AllowFallback
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".\\venv\\Scripts\\python.exe")) {
  throw "Expected venv at .\\venv. Activate/create venv first."
}

$env:DJANGO_SETTINGS_MODULE = "khatapro.settings"

# Ensure a clean dist output (PyInstaller may leave stale files in onedir builds).
$distRoot = "dist"
$bundleName = "JaisTechKhataBookDesktop"
$distDir = Join-Path -Path $distRoot -ChildPath $bundleName

$distPathArg = @()
if (Test-Path $distDir) {
  try {
    Remove-Item -Recurse -Force $distDir -ErrorAction Stop
  } catch {
    # If the user is currently running the EXE, files in dist can be locked (Access denied).
    # By default, fail fast so the final output stays at the stable dist path.
    $running = Get-Process -Name "JaisTechKhataBookDesktop" -ErrorAction SilentlyContinue
    if (-not $AllowFallback) {
      $pidInfo = ""
      if ($running) {
        $pids = ($running | Select-Object -ExpandProperty Id -Unique) -join ", "
        if ($pids) { $pidInfo = " (running PID(s): $pids)" }
      }
      throw "Could not remove $distDir (likely locked by the running desktop app$pidInfo). Close the app and rerun build, or run: .\\build_desktop.ps1 -AllowFallback"
    }

    # Optional fallback: build to a timestamped dist path so we can still build without killing the running app.
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $fallbackRoot = Join-Path -Path "dist_builds" -ChildPath ("$bundleName-$ts")
    New-Item -ItemType Directory -Force -Path $fallbackRoot | Out-Null
    $distPathArg = @("--distpath", $fallbackRoot)
    Write-Host "WARNING: Could not remove $distDir (likely locked). Building to: $fallbackRoot"
  }
}

try {
  .\venv\Scripts\python.exe -c "import PyInstaller; print(PyInstaller.__version__)"
  Write-Host "PyInstaller already installed."
} catch {
  Write-Host "Installing PyInstaller..."
  .\venv\Scripts\python.exe -m pip install -U pyinstaller
}

.\venv\Scripts\python.exe -m PyInstaller --noconfirm --clean @distPathArg desktop_app.spec

# PyInstaller leaves an intermediate `dist\JaisTechKhataBookDesktop.exe` next to the output folder.
# The distributable app is the EXE *inside* `dist\JaisTechKhataBookDesktop\` alongside `_internal\`.
$effectiveDistRoot = $distRoot
if ($distPathArg.Count -ge 2) {
  $effectiveDistRoot = $distPathArg[1]
}
$intermediateExe = Join-Path -Path $effectiveDistRoot -ChildPath "$bundleName.exe"
if (Test-Path $intermediateExe) {
  Remove-Item -Force $intermediateExe
}

Write-Host ""
$finalBundleDir = Join-Path -Path $effectiveDistRoot -ChildPath $bundleName
$finalExe = Join-Path -Path $finalBundleDir -ChildPath "$bundleName.exe"
Write-Host "Built bundle at: $finalBundleDir"
Write-Host "Run: $finalExe"
