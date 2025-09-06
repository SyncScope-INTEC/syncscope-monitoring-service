#!/bin/bash

# Exit on any error
set -e

echo "Starting SyncScope Monitoring Service..."

# Collect static files (this needs environment variables)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8002 --workers 3 --worker-class sync --timeout 120 config.wsgi:application