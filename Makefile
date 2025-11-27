# Vanna SQL Service - Makefile
# Quick commands for development and deployment

.PHONY: help start stop restart logs build clean test health train

# Default target
help:
	@echo "Vanna SQL Service - Available Commands"
	@echo "======================================"
	@echo "make start       - Start all services"
	@echo "make stop        - Stop all services"
	@echo "make restart     - Restart all services"
	@echo "make logs        - View service logs"
	@echo "make build       - Build Docker images"
	@echo "make clean       - Remove containers and volumes"
	@echo "make test        - Test API endpoints"
	@echo "make health      - Check service health"
	@echo "make train       - Trigger schema training"
	@echo "make shell       - Open shell in container"
	@echo "make db-shell    - Open PostgreSQL shell"

# Start services
start:
	@echo "🚀 Starting Vanna SQL Service..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "📡 API: http://localhost:8010"
	@echo "📚 Docs: http://localhost:8010/docs"
	@echo "🔍 Qdrant: http://localhost:6333/dashboard"

# Stop services
stop:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ Services stopped"

# Restart services
restart:
	@echo "🔄 Restarting services..."
	docker-compose restart
	@echo "✅ Services restarted"

# View logs
logs:
	docker-compose logs -f vanna-sql-service

# View all logs
logs-all:
	docker-compose logs -f

# Build images
build:
	@echo "🏗️ Building Docker images..."
	docker-compose build --no-cache
	@echo "✅ Build complete"

# Clean everything
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	@echo "✅ Cleanup complete"

# Test endpoints
test:
	@echo "🧪 Testing API endpoints..."
	@echo "\n1. Health Check:"
	@curl -s http://localhost:8010/health | python -m json.tool
	@echo "\n2. Trained Tables:"
	@curl -s http://localhost:8010/api/trained-tables | python -m json.tool

# Health check
health:
	@echo "❤️ Checking service health..."
	@curl -s http://localhost:8010/health | python -m json.tool

# Trigger training
train:
	@echo "🎓 Triggering schema training..."
	@curl -X POST http://localhost:8010/api/train-schema | python -m json.tool

# Open shell in container
shell:
	docker-compose exec vanna-sql-service /bin/bash

# Open database shell
db-shell:
	@echo "Enter database password when prompted..."
	@read -p "Database Host: " host; \
	read -p "Database Port: " port; \
	read -p "Database Name: " dbname; \
	read -p "Database User: " user; \
	psql -h $$host -p $$port -U $$user -d $$dbname

# View container status
status:
	docker-compose ps

# Install local development dependencies
dev-install:
	@echo "📦 Installing development dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Run local (without Docker)
dev-run:
	@echo "🏃 Running locally..."
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# Format code
format:
	@echo "✨ Formatting code..."
	black app/
	isort app/
	@echo "✅ Code formatted"

# Generate API client
generate-client:
	@echo "📝 Generating API client..."
	curl -s http://localhost:8010/openapi.json > openapi.json
	@echo "✅ OpenAPI spec saved to openapi.json"

# Backup Qdrant data
backup:
	@echo "💾 Backing up Qdrant data..."
	docker-compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
	docker cp $$(docker-compose ps -q qdrant):/tmp/qdrant-backup.tar.gz ./qdrant-backup-$$(date +%Y%m%d-%H%M%S).tar.gz
	@echo "✅ Backup complete"

# Pull latest images
pull:
	@echo "⬇️ Pulling latest images..."
	docker-compose pull
	@echo "✅ Images updated"

# Show environment
env:
	@echo "📋 Current environment:"
	@cat .env 2>/dev/null || echo "⚠️ .env file not found. Copy from .env.example"
