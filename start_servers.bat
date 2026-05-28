@echo off
title Video Conference Servers
echo Starting Video Conference Servers...
echo.

:: Kill any existing Django/Flask processes
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul

:: Prefer per-app virtual environments over root venv
set "DJANGO_VENV=%~dp0django_app\venv\Scripts\python.exe"
set "FLASK_VENV=%~dp0flask_app\venv\Scripts\python.exe"
set "ROOT_VENV=%~dp0venv\Scripts\python.exe"

if exist "%DJANGO_VENV%" ( set "DJANGO_PY=%DJANGO_VENV%" ) else ( set "DJANGO_PY=%ROOT_VENV%" )
if not exist "%DJANGO_PY%" set "DJANGO_PY=python"

if exist "%FLASK_VENV%" ( set "FLASK_PY=%FLASK_VENV%" ) else ( set "FLASK_PY=%ROOT_VENV%" )
if not exist "%FLASK_PY%" set "FLASK_PY=python"

:: Start Django
echo [1/2] Starting Django on http://localhost:8000 ...
start "Django" cmd /k "cd /d %~dp0\django_app && %DJANGO_PY% manage.py runserver 0.0.0.0:8000"

:: Start Flask
echo [2/2] Starting Flask on http://localhost:5000 ...
start "Flask" cmd /k "cd /d %~dp0\flask_app && %FLASK_PY% signaling_server.py"

echo.
echo Both servers started! Access the app at:
echo   User App:  http://localhost:8000
echo   Admin:     http://localhost:8000/admin/
echo.
echo Close the server windows to stop.
pause
