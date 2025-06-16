.PHONY: help install test lint format run docker-build docker-up docker-down migrate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run tests
	pytest supervisor_agent/tests/ -v --cov=supervisor_agent --cov-report=html

test-fast: ## Run tests without coverage
	pytest supervisor_agent/tests/ -v

lint: ## Run linting
	flake8 supervisor_agent/
	mypy supervisor_agent/

format: ## Format code
	black supervisor_agent/
	isort supervisor_agent/

run: ## Run the application locally
	uvicorn supervisor_agent.api.main:app --reload --host 0.0.0.0 --port 8000

run-worker: ## Run Celery worker
	python supervisor_agent/queue/celery_worker.py

run-beat: ## Run Celery beat scheduler
	celery -A supervisor_agent.queue.celery_app beat --loglevel=info

docker-build: ## Build Docker image
	docker-compose build

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down

docker-logs: ## View logs from all services
	docker-compose logs -f

docker-logs-api: ## View API logs
	docker-compose logs -f api

docker-logs-worker: ## View worker logs
	docker-compose logs -f worker

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration
	alembic revision --autogenerate -m "$(MESSAGE)"

db-reset: ## Reset database (development only)
	docker-compose down postgres
	docker volume rm $$(docker volume ls -q | grep postgres) || true
	docker-compose up -d postgres
	sleep 5
	make migrate

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/

setup-dev: ## Setup development environment
	pip install -r requirements.txt
	cp .env.sample .env
	echo "Please edit .env file with your configuration"

health-check: ## Check application health
	curl -f http://localhost:8000/api/v1/healthz || echo "Health check failed"

api-docs: ## Open API documentation
	open http://localhost:8000/docs