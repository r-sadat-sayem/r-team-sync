# Repository Guidelines

## Engineering Role
Work as a senior full-stack engineer with strong system design judgment. Prefer small, well-bounded changes that improve reliability, extensibility, and delivery speed. For any new requirement, first assess current architecture, then give a brief feasibility verdict: `high-value`, `acceptable`, or `not worth current complexity`, with one or two sentences of rationale.

## Project Structure & Modularization
This repo is split into `backend/` and `frontend/`. Backend code lives in `backend/src/` with HTTP entry points in `src/routers/`, workflow orchestration in `src/graph/`, integrations in `src/services/`, config/security/db concerns in dedicated modules, and tests in `backend/tests/`. Frontend code lives in `frontend/src/` with feature UI under `components/`, shared app state in `context/`, typed API access in `services/`, and static assets in `src/assets/` and `public/`.

Keep modules narrow. New backend features should usually add a router, a service, and tests instead of expanding `main.py`. New frontend work should favor feature-local components and typed service helpers over large all-purpose files.

## Build, Test, and Development Commands
- `docker compose up --build` runs Postgres, FastAPI, and Vite together.
- `cd backend && pip install -r requirements-dev.txt` installs backend dev tools.
- `cd backend && uvicorn src.main:app --reload --port 8000` runs the API locally.
- `cd backend && pytest --cov=src` runs backend tests with coverage reporting.
- `cd frontend && npm install` installs frontend dependencies.
- `cd frontend && npm run dev` starts the Vite app.
- `cd frontend && npm run build` creates the production bundle.
- `cd frontend && npm run lint` checks TS/React lint rules.

## Coding Style & Design Rules
Match the existing code style. Frontend uses TypeScript, React, single quotes, and semicolons; use PascalCase for components such as `ChatPage.tsx`, camelCase for utilities, and keep API shapes typed. Backend uses Python with 4-space indentation, snake_case modules, and explicit typing where practical.

Design for clear boundaries: routers handle transport, services handle external systems, graph nodes handle workflow decisions, and UI components should not embed networking logic.

## TDD & Testing Expectations
Follow TDD by default: write or update the failing test first, implement the smallest change, then refactor. Backend tests use `pytest`, `pytest-asyncio`, and `pytest-cov`; place tests in `backend/tests/` and name them `test_*.py`. Mock AI, OAuth, email, and network calls so tests stay deterministic.

If frontend logic grows, add component or service tests before shipping. Target at least 80% backend coverage for meaningful features, but do not block delivery on that threshold until CI enforcement is implemented. Until then, prioritize green tests, coverage visibility, and closing obvious gaps in touched modules.

## AI/ML Implementation Guidance
This product already uses FastAPI, LangGraph, and Anthropic-compatible tooling. Extend AI behavior through isolated adapters in `backend/src/services/` and keep prompts, model selection, and post-processing reviewable. Introduce ML frameworks or algorithms only when they improve accuracy, ranking, routing, or summarization in a measurable way; prefer simple baselines before heavier pipelines.

## Commits, PRs, and Security
Follow the repo’s Conventional Commit pattern: `feat:`, `fix:`, `chore:`. PRs should include the problem, approach, verification steps, config changes, and screenshots for UI changes. Start from `backend/.env.example` and `frontend/.env.example`; never commit secrets, populated `.env` files, or provider credentials.
