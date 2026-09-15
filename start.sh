#!/usr/bin/env bash
set -e

# Run database migrations first (creates tables on fresh Neon DB)
python manage.py migrate --no-input

# Create/update the admin superuser from DJANGO_SUPERUSER_* env vars
# (idempotent: skips if the superuser already exists)
python manage.py create_admin

# Start the production WSGI server
exec gunicorn messmgt.wsgi:application
