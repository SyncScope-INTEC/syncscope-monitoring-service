#!/bin/bash

# Exit on any failure
set -e

# Wait for database to be ready
echo "Waiting for database..."
python << END
import os
import sys
import time
import psycopg2
from urllib.parse import urlparse

db_url = os.environ.get('DATABASE_URL')
if db_url:
    result = urlparse(db_url)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port
    
    conn_params = {
        'host': hostname,
        'port': port,
        'user': username,
        'password': password,
        'database': database
    }
    
    while True:
        try:
            conn = psycopg2.connect(**conn_params)
            conn.close()
            print("Database is ready!")
            break
        except psycopg2.OperationalError:
            print("Database is unavailable - sleeping")
            time.sleep(1)
END

# Wait for Redis to be ready
echo "Waiting for Redis..."
python << END
import os
import sys
import time
import redis
from urllib.parse import urlparse

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')
result = urlparse(redis_url)

r = redis.Redis(
    host=result.hostname or 'localhost',
    port=result.port or 6379,
    db=int(result.path[1:]) if result.path else 1
)

while True:
    try:
        r.ping()
        print("Redis is ready!")
        break
    except redis.ConnectionError:
        print("Redis is unavailable - sleeping")
        time.sleep(1)
END

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"