.PHONY: help install dev test clean docker-build docker-up docker-down lint format migrate

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make dev           - Run development server with auto-reload"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean up cache files"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start all services with docker-compose"
	@echo "  make docker-down   - Stop all services"
	@echo "  make migrate       - Run database migrations"
	@echo "  make logs          - Show docker-compose logs"

# Install dependencies
install:
	pip install -r requirements.txt

# Run development server
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	pytest tests/ -v --cov=app --cov-report=html

# Run linters
lint:
	flake8 app/ --max-line-length=120
	mypy app/

# Format code
format:
	black app/ tests/
	isort app/ tests/

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

# Docker commands
docker-build:
	docker build -f deploy/Dockerfile -t admin-service:latest .

docker-up:
	cd ../.. && docker-compose up -d

docker-down:
	cd ../.. && docker-compose down

docker-logs:
	cd ../.. && docker-compose logs -f admin-service

# Database migrations
migrate:
	alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Create .env from example
env:
	cp .env.example .env
	@echo ".env file created. Please update with your configuration."

# Setup local development environment
setup: env install
	@echo "Setup complete! Run 'make dev' to start the development server."
