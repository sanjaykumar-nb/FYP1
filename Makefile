.PHONY: help up down build logs test lint format

# Default target
help:
	@echo "TeamSync AI - Development Commands"
	@echo ""
	@echo "  make up          - Start all services (docker-compose up)"
	@echo "make down         - Stop all services (docker-compose down)"
	@echo "make build        - Build all Docker images"
	@echo "make logs         - View logs from all services"
	@echo "make test         - Run tests for all services"
	@echo "make lint         - Run linting for all services"
	@echo "make format       - Format code for all services"
	@echo "make db-import    - Import a real sprint from the TAWOS dataset"
	@echo "make db-seed      - Seed database with demo data"
	@echo "make clean        - Clean up Docker volumes and images"

# Docker Compose
up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-ai:
	docker-compose logs -f ai-service

logs-frontend:
	docker-compose logs -f frontend

# Database
# Tables are created by the backend on startup, so there is no migration step to run.
db-seed:
	docker-compose exec backend python -m app.scripts.seed

db-import:
	docker-compose exec backend python -m app.scripts.import_real_sprint

db-reset:
	docker-compose down -v
	docker-compose up -d
	docker-compose exec backend python -m app.scripts.seed

# Testing
test:
	docker-compose exec backend pytest
	docker-compose exec ai-service pytest
	docker-compose exec frontend npm run test:ci

test-backend:
	docker-compose exec backend pytest -v

test-ai:
	docker-compose exec ai-service pytest -v

test-frontend:
	docker-compose exec frontend npm run test:ci

# Linting
lint:
	docker-compose exec backend ruff check .
	docker-compose exec ai-service ruff check .
	docker-compose exec frontend npm run lint

format:
	docker-compose exec backend ruff format .
	docker-compose exec ai-service ruff format .
	docker-compose exec frontend npm run format

# Development
dev-backend:
	docker-compose exec backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-ai:
	docker-compose exec ai-service uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

dev-frontend:
	docker-compose exec frontend npm run dev

# Cleanup
clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

clean-all:
	docker-compose down -v --remove-orphans
	docker system prune -af --volumes

# Production
prod-build:
	docker-compose -f docker-compose.prod.yml build

prod-up:
	docker-compose -f docker-compose.prod.yml up -d

prod-down:
	docker-compose -f docker-compose.prod.yml down