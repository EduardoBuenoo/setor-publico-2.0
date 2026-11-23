@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" python -m venv .venv || exit /b 1
set "SIGDEI_PYTHON=.venv\Scripts\python.exe"
"%SIGDEI_PYTHON%" -m pip install -r backend\requirements.txt || exit /b 1
"%SIGDEI_PYTHON%" backend\manage.py migrate --noinput || exit /b 1
"%SIGDEI_PYTHON%" backend\manage.py bootstrap_setores || exit /b 1
start "SIGDEI API" "%SIGDEI_PYTHON%" backend\manage.py runserver 127.0.0.1:8000
start "SIGDEI Frontend" "%SIGDEI_PYTHON%" -m http.server 5500 --bind 127.0.0.1 --directory frontend
echo SIGDEI em http://127.0.0.1:5500
echo Para o primeiro usuario execute .venv\Scripts\python.exe backend\manage.py bootstrap_admin
