@echo off
setlocal
cd /d %~dp0

:: Prefer per-app virtual environments
set "DJANGO_VENV=%~dp0django_app\venv"
set "FLASK_VENV=%~dp0flask_app\venv"
set "ROOT_VENV=%~dp0venv"

if exist "%DJANGO_VENV%\Scripts\activate.bat" (
    call "%DJANGO_VENV%\Scripts\activate.bat"
) else if exist "%ROOT_VENV%\Scripts\activate.bat" (
    call "%ROOT_VENV%\Scripts\activate.bat"
) else (
    echo Virtual environment not found. Create a venv first.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-cache-dir -r django_app\requirements.txt -r flask_app\requirements.txt
echo Applying Django migrations...
cd /d %~dp0\django_app
python manage.py migrate --noinput
cd /d %~dp0
echo Starting Django and Flask servers...
start "Django" cmd /k "cd /d %~dp0\django_app && python manage.py runserver 0.0.0.0:8000"
start "Flask" cmd /k "cd /d %~dp0\flask_app && python signaling_server.py"
echo.
echo Servers started. Open http://localhost:8000
echo Close the server windows to stop.
pause