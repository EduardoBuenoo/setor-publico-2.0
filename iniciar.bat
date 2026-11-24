
@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SIGDEI - Inicializador

cd /d "%~dp0"

set "BASE=%~dp0"
set "VENV=%BASE%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

echo.
echo ==========================================
echo       SIGDEI - SISTEMA DE GESTAO
echo ==========================================
echo.

:: 1. Verificar Python 3.12 ou 3.11
echo [1/6] Verificando Python...

if not exist "%PYTHON%" (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python Launcher nao encontrado.
        echo Instale Python 3.11 ou 3.12.
        pause
        exit /b 1
    )

    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_BASE=py -3.12"
    ) else (
        py -3.11 --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_BASE=py -3.11"
        ) else (
            echo [ERRO] Python 3.11 ou 3.12 nao encontrado.
            pause
            exit /b 1
        )
    )

    echo Criando ambiente virtual...
    %PYTHON_BASE% -m venv "%VENV%"

    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
)

if not exist "%PYTHON%" (
    echo [ERRO] Ambiente virtual nao encontrado.
    pause
    exit /b 1
)

:: 2. Instalar dependencias
echo.
echo [2/6] Instalando dependencias...

"%PYTHON%" -m pip install --upgrade pip

if errorlevel 1 (
    echo [ERRO] Falha ao atualizar o pip.
    pause
    exit /b 1
)

"%PYTHON%" -m pip install -r "%BASE%backend\requirements.txt"

if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

:: 3. Verificar Django
echo.
echo [3/6] Verificando projeto Django...

"%PYTHON%" "%BASE%backend\manage.py" check

if errorlevel 1 (
    echo [ERRO] O Django encontrou problemas.
    pause
    exit /b 1
)

:: 4. Aplicar migracoes
echo.
echo [4/6] Atualizando banco de dados...

"%PYTHON%" "%BASE%backend\manage.py" migrate

if errorlevel 1 (
    echo [ERRO] Falha ao aplicar migracoes.
    pause
    exit /b 1
)

:: 5. Iniciar backend
echo.
echo [5/6] Iniciando backend Django...

start "SIGDEI - BACKEND" /D "%BASE%backend" cmd /k ""%PYTHON%" manage.py runserver 127.0.0.1:8000"

timeout /t 4 /nobreak >nul

:: 6. Iniciar frontend
echo.
echo [6/6] Iniciando frontend...

start "SIGDEI - FRONTEND" cmd /k ""%PYTHON%" -m http.server 5500 --bind 127.0.0.1 --directory "%BASE%frontend""

timeout /t 3 /nobreak >nul

echo.
echo ==========================================
echo       SIGDEI INICIADO!
echo ==========================================
echo.
echo Frontend: http://127.0.0.1:5500/index.html
echo Backend:  http://127.0.0.1:8000
echo.
echo Mantenha as duas janelas abertas.
echo Para encerrar, feche as janelas do backend e frontend.
echo.

start "" "http://127.0.0.1:5500/index.html"

pause
