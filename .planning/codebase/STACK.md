# Technology Stack

**Analysis Date:** 2026-03-19

## Languages

**Primary:**
- TypeScript 5.3–5.9 - Frontend (`frontend/src`), planned backend (`backend/src`)
- JavaScript - n8n workflow JSON files (custom Code nodes use escaped JavaScript)

**Secondary:**
- HTML/CSS - `demo.html` standalone UI with inline styling
- Markdown - PRD document generation and project documentation

## Runtime

**Environment:**
- Node.js >=18.0.0 (required for both frontend dev and backend/planned implementation)
- Vite 8 dev server for frontend (http://localhost:5173)

**Package Manager:**
- npm 10+ (inferred from package-lock patterns)
- Lockfile: `frontend/package-lock.json` present

## Frameworks

**Frontend (Active):**
- React 19.2.4 - Component framework (`frontend/src/components`)
- React Router 7.13.1 - Routing (`frontend/src/App.tsx` with 6 routes: `/`, `/dashboard`, `/prd`, `/prd/:id`, `/email`, `/jira`)
- Vite 8.0.0 - Build tool and dev server
- TypeScript ~5.9.3 - Type safety (strict mode enabled in `frontend/tsconfig.app.json`)

**Frontend Utilities:**
- react-markdown 10.1.0 - Markdown rendering for PRD documents
- remark-gfm 4.0.1 - GitHub Flavored Markdown support
- Tailwind CSS 4.2.1 - Styling framework
- Lucide React 0.577.0 - Icon library
- clsx 2.1.1 + tailwind-merge 3.5.0 - Conditional CSS class utilities

**Backend (Planned, not yet implemented):**
- Express 4.18.2 - API server
- TypeScript 5.3.3 - Type safety (strict mode in `backend/tsconfig.json`)
- Node.js web server framework

**n8n Workflow Runtime:**
- n8n LangChain integration (`@n8n/n8n-nodes-langchain.*`)
  - Chat Trigger node - webhook entry point
  - Agent node - multi-turn conversation handling
  - LM Chat Ollama node - LLM interaction
  - Memory Buffer Window - session-based context management

## Key Dependencies

**Critical:**
- express 4.18.2 - HTTP server foundation (backend plan)
- react 19.2.4 - UI rendering engine (active frontend)
- typescript 5.3+ - Type system and compilation (all projects)

**Database & ORM:**
- pg 8.11.3 - PostgreSQL client (backend plan)

**AI/LLM Integration:**
- openai 4.20.1 - OpenAI API client (backend plan, optional provider)
- @anthropic-ai/sdk 0.24.3 - Anthropic Claude API client (backend plan, optional provider)

**WebSocket & Real-time:**
- ws 8.14.2 - WebSocket support (backend plan for real-time chat/notifications)

**Email & Communication:**
- nodemailer 6.9.7 - Email delivery (backend plan, n8n currently handles via Gmail node)

**Utilities:**
- uuid 9.0.1 - Session and document ID generation (backend plan)
- dotenv 16.3.1 - Environment configuration (backend plan, frontend uses Vite import.meta.env)
- zod 3.22.4 - Runtime schema validation (backend plan)

**Security & Middleware:**
- helmet 7.1.0 - Security headers (backend plan)
- cors 2.8.5 - CORS handling (backend plan)
- express-rate-limit 7.1.5 - Rate limiting (backend plan)

**Logging:**
- winston 3.11.0 - Structured logging (backend plan)

## Development Dependencies

**Frontend:**
- @vitejs/plugin-react 6.0.0 - React JSX transformation for Vite
- eslint 9.39.4 - Code linting
- @eslint/js 9.39.4 - ESLint base config
- typescript-eslint 8.56.1 - TypeScript linting rules
- eslint-plugin-react-hooks 7.0.1 - React hooks linting
- eslint-plugin-react-refresh 0.5.2 - Vite fast refresh validation
- autoprefixer 10.4.27 - CSS vendor prefixing for Tailwind
- postcss 8.5.8 - CSS processing pipeline for Tailwind

**Backend (Planned):**
- tsx 4.7.0 - TypeScript execution with hot reload (`npm run dev`)
- jest 29.7.0 - Unit testing framework
- ts-jest 29.1.1 - TypeScript support for Jest
- @types/* - Type definitions for Express, Node, PostgreSQL, WebSocket, Jest, etc.

## Configuration

**Frontend Environment:**
- Located: `frontend/.env` (create manually; example available in CLAUDE.md)
- Variables:
  - `VITE_N8N_BASE_URL` - n8n server address (default: http://localhost:5678)
  - `VITE_CHAT_WEBHOOK_ID` - Chat Trigger webhook ID from n8n
  - `VITE_EMAIL_WEBHOOK_ID` - Email form Wait node webhook ID (d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f)
  - `VITE_JIRA_WEBHOOK_ID` - JIRA approval form webhook ID

**Backend Environment (Planned):**
- Located: `backend/.env` (example at `backend/.env.example`)
- Key variables:
  - `PORT` - Express server port (default: 3000)
  - `NODE_ENV` - Environment (development/production)
  - `DATABASE_URL` or `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection
  - `AI_PROVIDER` - 'openai' or 'claude'
  - `OPENAI_API_KEY`, `OPENAI_MODEL` - OpenAI config
  - `CLAUDE_API_KEY`, `CLAUDE_MODEL` - Claude config
  - `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_ID`, `JIRA_ASSIGNEE_ID` - JIRA integration
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM_*` - Gmail SMTP config
  - `WS_PORT`, `WS_PATH` - WebSocket configuration
  - `CORS_ORIGIN` - Allowed origins (comma-separated)
  - `RATE_LIMIT_WINDOW_MS`, `RATE_LIMIT_MAX_REQUESTS` - Rate limiting config

**Build Configuration:**
- `frontend/vite.config.ts` - Vite build with @vitejs/plugin-react
- `frontend/tsconfig.json` - References `tsconfig.app.json` (app code) and `tsconfig.node.json` (build config)
- `frontend/tsconfig.app.json` - Strict TypeScript compilation targeting ES2023, JSX as react-jsx
- `frontend/eslint.config.js` - Flat ESLint config with React hooks and TypeScript rules

**Backend Configuration (Planned):**
- `backend/tsconfig.json` - Strict TypeScript targeting ES2022, CommonJS output
- ESLint config (not yet present in codebase)

## n8n Configuration

**Active Workflow:** `team_sync_dev_v2.1_with_JIRA.json` (34 KB, 26 nodes)

**LLM Setup:**
- Primary LLM: Ollama (`@n8n/n8n-nodes-langchain.lmChatOllama`)
  - Model: `gpt-oss:20b-cloud`
  - Temperature: 0.2
  - Max tokens: 8000
  - Credential ID: `Ro4RyNcsDpqjzjd0`
- Fallback model: `mistral:latest` (documented in CLAUDE.md but not active in current workflow)

**Memory & Sessions:**
- LLM Memory node: Memory Buffer Window with 20-turn context window
- Session key: `$json.sessionId` (passed from frontend)

**Integration Credentials (hardcoded in workflow):**
- Gmail credential ID: `euztR3CaCKVVRcH9`
- JIRA credential ID: `LIpsYPvVhobVTK8i`
- Ollama credential ID: `Ro4RyNcsDpqjzjd0`

**Webhook Endpoints:**
- Chat Trigger webhook: Variable (set via `VITE_CHAT_WEBHOOK_ID`)
- Email form Resume webhook: `d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f` (fixed)
- JIRA approval form webhook: Variable (set via `VITE_JIRA_WEBHOOK_ID`)

## Platform Requirements

**Development:**
- Node.js >=18.0.0
- npm 10+
- macOS/Linux/Windows with terminal access
- Text editor or IDE (VSCode recommended for TypeScript support)
- n8n instance running locally at `http://localhost:5678` (for webhook testing)
- Ollama running locally with `gpt-oss:20b-cloud` model loaded (for n8n workflows)

**Frontend-Only Development:**
- `cd frontend && npm install && npm run dev` starts Vite dev server
- No backend required for frontend dev (uses n8n webhooks directly)

**Production (Planned):**
- Node.js >=18.0.0
- PostgreSQL database
- n8n instance (self-hosted or cloud)
- JIRA instance with API token access
- Gmail account with app password (for email delivery)
- Ollama or other LLM provider (for n8n agent)

---

*Stack analysis: 2026-03-19*
