.PHONY: build up down logs ps clean

# Development commands
dev: build up

build:
	docker compose up --build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v

db-shell:
	docker compose exec postgres psql -U $$(grep POSTGRES_USER .env | cut -d '=' -f2) -d $$(grep POSTGRES_DB .env | cut -d '=' -f2)

# Production commands
prod-up:
	docker compose up --build -f docker compose.yaml -f docker compose.prod.yaml

prod-down:
	docker compose down -v -f docker compose.yaml -f docker compose.prod.yaml

prod-logs:
	docker compose logs -f -f docker compose.yaml -f docker compose.prod.yaml

prod-ps:
	docker compose ps -f docker compose.yaml -f docker compose.prod.yaml

# Database commands
db-backup:
	@mkdir -p backups
	docker compose exec -T postgres pg_dump -U $$(grep POSTGRES_USER .env | cut -d '=' -f2) -d $$(grep POSTGRES_DB .env | cut -d '=' -f2) > backups/backup_`date +%Y%m%d_%H%M%S`.sql

db-restore:
	@if [ -z "${FILE}" ]; then \
		echo "Please specify the backup file with FILE=path/to/backup.sql"; \
		exit 1; \
	fi
	docker compose exec -T postgres psql -U $$(grep POSTGRES_USER .env | cut -d '=' -f2) -d $$(grep POSTGRES_DB .env | cut -d '=' -f2) < ${FILE}

# Utility commands
shell:
	docker compose exec backend flask shell

migrate:
	docker compose exec backend flask db migrate -m "${MESSAGE}"

upgrade:
	docker compose exec backend flask db upgrade

downgrade:
	docker compose exec backend flask db downgrade

# Linting and testing
lint:
	docker compose exec backend flake8 .

test:
	docker compose exec backend python -m pytest

# Cleanup
prune:
	docker system prune -a --volumes

# Help
docs:
	@echo "Available commands:"
	@echo "  make dev         - Build and start development environment"
	@echo "  make prod-up     - Start production environment"
	@echo "  make down       - Stop all containers"
	@echo "  make logs       - View container logs"
	@echo "  make db-shell   - Open database shell"
	@echo "  make migrate    - Create a new migration"
	@echo "  make upgrade    - Upgrade database"
	@echo "  make downgrade  - Downgrade database"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linter"
	@echo "  make clean      - Remove all containers and volumes"
