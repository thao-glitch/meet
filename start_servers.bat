@echo off
title Video Conference Servers
echo Starting Video Conference Servers...
echo.

:: Kill any existing Django/Flask processes
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul

:: Use workspace virtual environment if available
set "VENV_PY=%~dp0venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    set "PYTHON=%VENV_PY%"
) else (
    set "PYTHON=python"
)

:: Start Django
echo [1/2] Starting Django on http://localhost:8000 ...
start "Django" cmd /k "cd /d %~dp0\django_app && "%PYTHON%" manage.py runserver 0.0.0.0:8000"

:: Start Flask
echo [2/2] Starting Flask on http://localhost:5000 ...
start "Flask" cmd /k "cd /d %~dp0\flask_app && "%PYTHON%" signaling_server.py"

echo.
echo Both servers started! Access the app at:
echo   User App:  http://localhost:8000
echo   Admin:     http://localhost:8000/admin/
echo.
echo Close the server windows to stop.
pause
