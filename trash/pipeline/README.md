# TeamSync AI — Pipeline Directory

All shell scripts, Docker Compose files, Nginx configs, and CI/CD workflows live here.
The `Makefile` at this directory's root is your single entry point for every environment.

## Quick Start

```bash
# 1. Copy and fill environment variables
cp pipeline/docker/.env.example .env

# 2. One-time setup (generates secrets, creates Docker volumes)
make setup

# 3. Start full dev stack (n8n + backend + frontend + postgres)
make dev

# 4. Open services
#   Frontend:  http://localhost:3000
#   Backend:   http://localhost:8000/docs
#   n8n:       http://localhost:5678
#   Demo page: http://localhost:4040
```

## Directory Structure

```
pipeline/
├── README.md               ← this file
├── Makefile                ← all make targets
├── scripts/
│   ├── setup.sh            ← one-time environment setup
│   ├── dev.sh              ← start dev stack
│   ├── build.sh            ← build all Docker images
│   ├── deploy.sh           ← deploy to production server
│   ├── backup.sh           ← backup PostgreSQL + n8n data
│   ├── export-workflows.sh ← export n8n workflows to JSON
│   └── import-workflows.sh ← import n8n workflows from JSON
├── ci-cd/
│   ├── ci.yml              ← GitHub Actions: lint + test + build on PR
│   ├── deploy-staging.yml  ← GitHub Actions: deploy on push to develop
│   └── deploy-prod.yml     ← GitHub Actions: deploy on push to main
├── nginx/
│   ├── nginx.conf          ← production (SSL termination, all services)
│   └── nginx.dev.conf      ← dev (no SSL, simple proxy)
├── docker/
│   ├── docker-compose.yml      ← production stack
│   ├── docker-compose.dev.yml  ← development stack (hot-reload)
│   ├── docker-compose.demo.yml ← demo page only (replaces root file)
│   └── .env.example            ← all required environment variables
└── docs/
    ├── architecture.md     ← system architecture + data flow
    ├── setup.md            ← first-time setup walkthrough
    └── api.md              ← FastAPI endpoint reference
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make setup` | One-time: generate secrets, init volumes, copy .env |
| `make dev` | Start development stack with hot-reload |
| `make dev-down` | Stop development stack |
| `make build` | Build all Docker images |
| `make prod` | Start production stack |
| `make prod-down` | Stop production stack |
| `make demo` | Start demo page only (points at local n8n) |
| `make backup` | Backup database + n8n data to `./backups/` |
| `make export-workflows` | Export n8n workflows to `./n8n/workflows/` |
| `make import-workflows` | Import workflows from `./n8n/workflows/` into n8n |
| `make logs` | Tail all container logs |
| `make logs-backend` | Tail FastAPI logs |
| `make logs-n8n` | Tail n8n logs |
| `make db-migrate` | Run Alembic migrations |
| `make db-shell` | Open psql shell |
| `make test` | Run all tests (backend + frontend) |
| `make lint` | Run all linters |

## Environment Variables

Copy `pipeline/docker/.env.example` to `.env` at the project root and fill in:

- `N8N_ENCRYPTION_KEY` — 32-char random string (generate with `make setup`)
- `DB_PASSWORD` — PostgreSQL password
- `BACKEND_API_KEY` — shared API key for frontend → backend calls
- `OLLAMA_BASE_URL` — URL to your Ollama instance (e.g. `http://host.docker.internal:11434`)
- `JIRA_*` — JIRA credentials (configured in n8n Credentials Manager after import)
- `GMAIL_*` — Gmail OAuth (configured in n8n Credentials Manager after import)

See `pipeline/docs/setup.md` for a full walkthrough.
