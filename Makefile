# Makefile for SyncScope Monitoring Service

.PHONY: help install test test-verbose coverage lint format check migrate run docker-build docker-run clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run tests
	python -m pytest

test-verbose: ## Run tests with verbose output
	python -m pytest -v

coverage: ## Run tests with coverage report
	python -m pytest --cov=apps.monitoring --cov-report=html --cov-report=term

lint: ## Run linting with ruff
	ruff check .

format: ## Format code with ruff
	ruff format .

check: lint test ## Run linting and tests

migrate: ## Run Django migrations
	python manage.py migrate

makemigrations: ## Create Django migrations
	python manage.py makemigrations

collectstatic: ## Collect static files
	python manage.py collectstatic --noinput

run: ## Run development server
	python manage.py runserver 0.0.0.0:8002

celery-worker: ## Run Celery worker
	celery -A config worker --loglevel=info

celery-beat: ## Run Celery beat scheduler
	celery -A config beat --loglevel=info

shell: ## Open Django shell
	python manage.py shell

docker-build: ## Build Docker image
	docker build -t syncscope-monitoring-service .

docker-run: ## Run with Docker Compose
	docker-compose up -d

docker-dev: ## Run development environment with Docker Compose
	docker-compose -f docker-compose.yml up

docker-prod: ## Run production environment with Docker Compose
	docker-compose -f docker-compose.prod.yml up -d

docker-stop: ## Stop Docker Compose services
	docker-compose down

docker-logs: ## View Docker Compose logs
	docker-compose logs -f

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/

setup-dev: install migrate ## Setup development environment
	python manage.py collectstatic --noinput

health-check: ## Check service health
	curl -f http://localhost:8002/monitoring/health/ || exit 1

api-docs: ## Open API documentation
	@echo "API Documentation available at:"
	@echo "  Swagger UI: http://localhost:8002/api/docs/"
	@echo "  ReDoc: http://localhost:8002/api/redoc/"
	@echo "  OpenAPI Schema: http://localhost:8002/api/schema/"