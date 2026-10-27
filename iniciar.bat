
@echo off
setlocal
title SIGDEI - Inicializador

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

echo ================================
echo        INICIANDO SIGDEI
echo ================================
echo.

if not exist "%PYTHON%" (
    echo ERRO: Python do ambiente virtual nao encontrado.
    echo Caminho: "%PYTHON%"
    pause
    exit /b 1
)

echo Iniciando backend Django...
start "SIGDEI - BACKEND" /D "%ROOT%backend" cmd /k ""%PYTHON%" manage.py runserver 127.0.0.1:8000"

timeout /t 3 /nobreak >nul

echo Iniciando frontend...
start "SIGDEI - FRONTEND" cmd /k ""%PYTHON%" -m http.server 5500 --directory "%ROOT%frontend""

timeout /t 2 /nobreak >nul

echo Abrindo SIGDEI no navegador...
start "" "http://127.0.0.1:5500/index.html"

echo.
echo SIGDEI iniciado. Mantenha as janelas abertas.
exit /b 0
