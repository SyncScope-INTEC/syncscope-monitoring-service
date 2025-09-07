# Use Python 3.11 slim image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gcc \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Change ownership of the app directory to django user
RUN chown -R django:django /app

# Switch to non-root user
USER django

# Expose port (Railway dynamically assigns PORT)
EXPOSE 8002

# Health check (use simple health endpoint to avoid database dependency)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:' + __import__('os').getenv('PORT', '8002') + '/simple-health/', timeout=10)"

# Create startup script to collect static files and run server
COPY --chown=django:django start.sh /app/
RUN chmod +x /app/start.sh

# Default command
CMD ["/app/start.sh"]