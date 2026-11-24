#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/manage.py migrate --noinput
.venv/bin/python backend/manage.py bootstrap_setores
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT
printf '%s\n' 'SIGDEI em http://127.0.0.1:5500' 'Primeiro usuário: .venv/bin/python backend/manage.py bootstrap_admin'
.venv/bin/python -m http.server 5500 --bind 127.0.0.1 --directory frontend
