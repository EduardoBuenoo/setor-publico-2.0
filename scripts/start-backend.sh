#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py bootstrap_setores
python manage.py collectstatic --noinput
exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-2}" --timeout 90
