#!/bin/sh
# Web container start: migrate, optionally load demo data, then serve.
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --timeout 120 --access-logfile -
