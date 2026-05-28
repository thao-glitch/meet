Write-Host "Starting Video Conference Servers..." -ForegroundColor Green

$djangoDir = Join-Path $PSScriptRoot "django_app"
$flaskDir = Join-Path $PSScriptRoot "flask_app"

# Prefer per-app virtual environments over root venv
$djangoVenv = Join-Path $djangoDir "venv\Scripts\python.exe"
$flaskVenv = Join-Path $flaskDir "venv\Scripts\python.exe"
$rootVenv = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

$djangoPython = if (Test-Path $djangoVenv) { $djangoVenv } elseif (Test-Path $rootVenv) { $rootVenv } else { "python" }
$flaskPython = if (Test-Path $flaskVenv) { $flaskVenv } elseif (Test-Path $rootVenv) { $rootVenv } else { "python" }

# Kill any existing processes on these ports
Get-Process -Name python* -ErrorAction SilentlyContinue | ForEach-Object {
    try { $cmd = $_.CommandLine } catch { $cmd = "" }
    if ($cmd -match "manage.py runserver|signaling_server") {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1

# Start Django
$djangoJob = Start-Process -NoNewWindow -PassThru -FilePath $djangoPython -ArgumentList "manage.py runserver 0.0.0.0:8000" -WorkingDirectory $djangoDir
Write-Host "Django starting on http://localhost:8000" -ForegroundColor Cyan

# Start Flask
$flaskJob = Start-Process -NoNewWindow -PassThru -FilePath $flaskPython -ArgumentList "signaling_server.py" -WorkingDirectory $flaskDir
Write-Host "Flask starting on http://localhost:5000" -ForegroundColor Cyan

Write-Host ""
Write-Host "Servers started! Access the app at:" -ForegroundColor Green
Write-Host "  User App:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Admin:     http://localhost:8000/admin/" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to stop both servers..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Cleanup
Stop-Process -Id $djangoJob.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $flaskJob.Id -Force -ErrorAction SilentlyContinue
Write-Host "Servers stopped." -ForegroundColor Red
