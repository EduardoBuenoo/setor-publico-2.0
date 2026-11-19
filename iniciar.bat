@echo off
setlocal
title SIGDEI - Inicializador local

set "BASE=%~dp0"
set "PYTHON=%BASE%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
        set "PYTHON=%LOCALAPPDATA%\Python\bin\python.exe"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON=py"
        ) else (
            set "PYTHON=python"
        )
    )
)

echo ================================
echo        INICIANDO SIGDEI
echo ================================
echo.

echo Iniciando backend Django...
start "SIGDEI - BACKEND" /D "%BASE%backend" cmd /k ""%PYTHON%" manage.py runserver 127.0.0.1:8000"

timeout /t 3 /nobreak >nul

echo Iniciando frontend...
start "SIGDEI - FRONTEND" cmd /k ""%PYTHON%" -m http.server 5500 --bind 127.0.0.1 --directory "%BASE%frontend""

timeout /t 2 /nobreak >nul

echo Abrindo SIGDEI no navegador...
start "" "http://127.0.0.1:5500/index.html"

echo.
echo SIGDEI iniciado. Mantenha as janelas abertas.
exit /b 0
