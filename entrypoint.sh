#!/bin/sh
# entrypoint.sh
# Runs on every container start. migrate + collectstatic need real env
# vars (SECRET_KEY, DB credentials, etc.) which only exist at container
# runtime in Container Apps, not at image build time — that's why these
# happen here rather than as Dockerfile RUN steps.
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
# source.css is Tailwind's uncompiled build input (uses the @import
# "tailwindcss" build directive, not real CSS) — never served, and its
# @import confuses whitenoise's post-processor if swept up here. Only
# the compiled output.css is ever referenced by templates.
python manage.py collectstatic --noinput --ignore=source.css

echo "Starting gunicorn..."
exec gunicorn itca_sms.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60
