# TeamSync AI — Makefile
# Run `make help` to see all available targets.
# All commands run from the project root.

ROOT_DIR := $(shell pwd)
COMPOSE_DEV := -f pipeline/docker/docker-compose.dev.yml
COMPOSE_PROD := -f pipeline/docker/docker-compose.yml
COMPOSE_DEMO := -f pipeline/docker/docker-compose.demo.yml
ENV_FILE := --env-file .env

.DEFAULT_GOAL := help

# ── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "TeamSync AI — Available Make Targets"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: setup
setup: ## One-time environment setup (generates secrets, copies .env)
	@bash pipeline/scripts/setup.sh

# ── Development ───────────────────────────────────────────────────────────────
.PHONY: dev
dev: ## Start full development stack (n8n + backend + frontend + postgres)
	@bash pipeline/scripts/dev.sh

.PHONY: dev-down
dev-down: ## Stop development stack
	docker compose $(COMPOSE_DEV) $(ENV_FILE) down

.PHONY: dev-rebuild
dev-rebuild: ## Rebuild and restart dev stack (use after dep changes)
	docker compose $(COMPOSE_DEV) $(ENV_FILE) up --build -d

# ── Demo page ─────────────────────────────────────────────────────────────────
.PHONY: demo
demo: ## Start demo landing page only (port 4040, proxies to local n8n)
	docker compose $(COMPOSE_DEMO) $(ENV_FILE) up --build -d
	@echo "Demo running at http://localhost:4040"

.PHONY: demo-down
demo-down: ## Stop demo container
	docker compose $(COMPOSE_DEMO) $(ENV_FILE) down

# ── Build ─────────────────────────────────────────────────────────────────────
.PHONY: build
build: ## Build all Docker images
	@bash pipeline/scripts/build.sh

# ── Production ────────────────────────────────────────────────────────────────
.PHONY: prod
prod: ## Start production stack
	docker compose $(COMPOSE_PROD) $(ENV_FILE) up -d

.PHONY: prod-down
prod-down: ## Stop production stack
	docker compose $(COMPOSE_PROD) $(ENV_FILE) down

.PHONY: deploy
deploy: ## Deploy to production server (requires SSH config in .env)
	@bash pipeline/scripts/deploy.sh

# ── Database ──────────────────────────────────────────────────────────────────
.PHONY: db-migrate
db-migrate: ## Run Alembic database migrations
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend alembic upgrade head

.PHONY: db-rollback
db-rollback: ## Roll back last Alembic migration
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend alembic downgrade -1

.PHONY: db-shell
db-shell: ## Open interactive psql shell
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec postgres \
	  psql -U $${DB_USER:-n8n} -d $${DB_NAME:-teamsync}

.PHONY: db-seed
db-seed: ## Seed database with dev data
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend python -m src.scripts.seed

# ── n8n Workflows ─────────────────────────────────────────────────────────────
.PHONY: export-workflows
export-workflows: ## Export all n8n workflows to ./n8n/workflows/
	@bash pipeline/scripts/export-workflows.sh

.PHONY: import-workflows
import-workflows: ## Import workflows from ./n8n/workflows/ into n8n
	@bash pipeline/scripts/import-workflows.sh

# ── Testing ───────────────────────────────────────────────────────────────────
.PHONY: test
test: ## Run all tests (backend pytest + frontend jest/vitest)
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend pytest tests/ -v
	cd frontend && npm test -- --run

.PHONY: test-backend
test-backend: ## Run backend tests only
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend pytest tests/ -v --tb=short

.PHONY: test-frontend
test-frontend: ## Run frontend tests only
	cd frontend && npm test -- --run

# ── Linting ───────────────────────────────────────────────────────────────────
.PHONY: lint
lint: ## Run all linters (ruff + mypy + eslint)
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend ruff check src/ tests/
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend mypy src/
	cd frontend && npm run lint

.PHONY: lint-fix
lint-fix: ## Auto-fix lint issues where possible
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend ruff check --fix src/ tests/
	cd frontend && npm run lint -- --fix

# ── Logs ──────────────────────────────────────────────────────────────────────
.PHONY: logs
logs: ## Tail all container logs
	docker compose $(COMPOSE_DEV) $(ENV_FILE) logs -f

.PHONY: logs-backend
logs-backend: ## Tail FastAPI backend logs
	docker compose $(COMPOSE_DEV) $(ENV_FILE) logs -f backend

.PHONY: logs-n8n
logs-n8n: ## Tail n8n logs
	docker compose $(COMPOSE_DEV) $(ENV_FILE) logs -f n8n

.PHONY: logs-frontend
logs-frontend: ## Tail frontend logs
	docker compose $(COMPOSE_DEV) $(ENV_FILE) logs -f frontend

# ── Backup ────────────────────────────────────────────────────────────────────
.PHONY: backup
backup: ## Backup PostgreSQL + n8n data to ./backups/
	@bash pipeline/scripts/backup.sh

# ── Utilities ─────────────────────────────────────────────────────────────────
.PHONY: ps
ps: ## Show running containers
	docker compose $(COMPOSE_DEV) $(ENV_FILE) ps

.PHONY: clean
clean: ## Remove stopped containers and unused images
	docker compose $(COMPOSE_DEV) $(ENV_FILE) down --remove-orphans
	docker image prune -f

.PHONY: shell-backend
shell-backend: ## Open shell in backend container
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec backend bash

.PHONY: shell-n8n
shell-n8n: ## Open shell in n8n container
	docker compose $(COMPOSE_DEV) $(ENV_FILE) exec n8n sh
