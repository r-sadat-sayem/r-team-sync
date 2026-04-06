# Repository Guidelines

## Project Structure & Module Organization
This repository is split into `frontend/` and `backend/`.

- `frontend/src/components/` holds feature UI such as `chat/`, `prd/`, `jira/`, `email/`, `dashboard/`, `layout/`, and shared `ui/`.
- `frontend/src/context/`, `services/`, `types/`, and `styles/` contain app state, API helpers, shared types, and global styling.
- `frontend/public/` and `frontend/src/assets/` store static assets.
- `backend/src/` is organized for `config/`, `controllers/`, `middleware/`, `models/`, `routes/`, `services/`, and `types/`.
- `backend/migrations/001_initial.sql` contains the current database migration. `backend/tests/` exists for backend tests, though test files are not committed yet.

## Build, Test, and Development Commands
Run commands from the relevant package directory.

- `cd frontend && npm install && npm run dev`: start the Vite dev server on `localhost:5173`.
- `cd frontend && npm run build`: run TypeScript project build and create a production bundle.
- `cd frontend && npm run lint`: lint all frontend `ts` and `tsx` files with ESLint.
- `cd backend && npm install && npm run dev`: start the backend with `tsx watch src/app.ts`.
- `cd backend && npm run build`: compile backend TypeScript to `dist/`.
- `cd backend && npm run test`: run Jest tests.
- `cd backend && npm run db:migrate`: apply SQL and script-driven migrations.

## Coding Style & Naming Conventions
Use TypeScript throughout. Frontend code currently uses 2-space indentation, semicolons, PascalCase React component files (`ChatInterface.tsx`), and camelCase utilities/services (`api.ts`). Keep feature code grouped by domain under `frontend/src/components/<feature>/`. Run `frontend` ESLint before opening a PR. Backend `tsconfig.json` is strict; avoid unused locals, implicit `any`, and unchecked null handling.

## Testing Guidelines
Backend testing is configured for Jest; add tests under `backend/tests/` with names like `feature-name.test.ts`. No frontend test runner is configured in this branch, so at minimum verify changed flows with `npm run build` and `npm run lint` in `frontend`. For backend changes, run `npm run typecheck` and `npm run test`.

## Commit & Pull Request Guidelines
`git log` shows no committed history on this branch yet, so no repository-specific commit convention is established. Use short imperative subjects such as `Add Jira approval form validation`. Keep PRs focused, describe user-visible changes, list config or migration impacts, and include screenshots for frontend UI updates.

## Security & Configuration Tips
Do not commit filled `.env` files or API tokens. Use `frontend/.env` for `VITE_*` webhook settings and `backend/.env` for database, AI provider, SMTP, and JIRA credentials based on `backend/.env.example`.
