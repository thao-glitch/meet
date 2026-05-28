Write-Host "Starting Video Conference Servers..." -ForegroundColor Green

$djangoDir = Join-Path $PSScriptRoot "django_app"
$flaskDir = Join-Path $PSScriptRoot "flask_app"

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

# Kill any existing processes on these ports
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "manage.py runserver"
} | Stop-Process -Force -ErrorAction SilentlyContinue

Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "signaling_server.py"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Start Django
$djangoJob = Start-Process -NoNewWindow -PassThru -FilePath $python -ArgumentList "manage.py runserver 0.0.0.0:8000" -WorkingDirectory $djangoDir
Write-Host "Django starting on http://localhost:8000" -ForegroundColor Cyan

# Start Flask
$flaskJob = Start-Process -NoNewWindow -PassThru -FilePath $python -ArgumentList "signaling_server.py" -WorkingDirectory $flaskDir
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
