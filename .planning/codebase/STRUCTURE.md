# STRUCTURE.md

Directory layout, key file locations, and where to add new code.

---

## Top-Level Layout

```
v1.1/
├── frontend/                  # React/TypeScript/Vite SPA
├── team_sync_dev_v2.1_with_JIRA.json  # PRIMARY active workflow
├── team_sync_dev_v2.1.json    # v2.1 without JIRA
├── team_sync_dev_v2.0.json    # previous version
├── main.json                  # Gen 1 orchestrator
├── task_agent.json            # Gen 1 subworkflow
├── prd_creator_agent.json     # Gen 1 subworkflow
├── team-sync-ai-agent-conversational.json
├── demo.html                  # Standalone @n8n/chat widget
├── ArchitectureDiagram.txt    # ASCII workflow diagram
├── CLAUDE.md                  # Claude Code instructions
├── BACKEND_PLAN.md            # Planned rewrite (not implemented)
├── FRONTEND_DESIGN.md         # UI design spec (aspirational)
├── DEMO_GUIDE.md              # Demo walkthrough
└── .planning/codebase/        # GSD codebase map (this directory)
```

---

## Frontend Source Tree (`frontend/src/`)

```
src/
├── main.tsx                   # Vite entry — mounts AppProvider + Router
├── App.tsx                    # Route definitions (6 routes)
├── App.css                    # Minimal global overrides
├── index.css                  # Tailwind CSS directives
├── styles/
│   └── globals.css            # Extended global styles
├── types/
│   └── index.ts               # ALL shared TypeScript types
├── services/
│   └── api.ts                 # TeamSyncAPI singleton — all I/O
├── context/
│   └── AppContext.tsx         # Global state (AppProvider + useApp hook)
└── components/
    ├── chat/
    │   └── ChatInterface.tsx  # Main chat UI, message list, input
    ├── prd/
    │   └── PRDViewer.tsx      # PRD list (/prd) and detail (/prd/:id)
    ├── email/
    │   └── EmailForm.tsx      # Email delivery form
    ├── jira/
    │   └── JIRATicketViewer.tsx  # JIRA ticket display
    ├── dashboard/
    │   └── Dashboard.tsx      # Overview (/dashboard)
    ├── layout/
    │   ├── Layout.tsx         # Shell with Sidebar + Header
    │   ├── Sidebar.tsx        # Navigation sidebar
    │   └── Header.tsx         # Top header bar
    └── ui/
        ├── Button.tsx         # Reusable button (clsx + tailwind-merge)
        ├── Card.tsx           # Card container
        └── Input.tsx          # Input field
```

---

## Routes

| Path | Component | Notes |
|---|---|---|
| `/` | `ChatInterface` | Main entry — PRD generation flow |
| `/dashboard` | `Dashboard` | Session overview |
| `/prd` | `PRDViewer` | PRD history list |
| `/prd/:id` | `PRDViewer` | Single PRD detail |
| `/email` | `EmailForm` | Manual email trigger |
| `/jira` | `JIRATicketViewer` | JIRA ticket browser |

---

## Key File Locations

| What | Where |
|---|---|
| TypeScript types | `frontend/src/types/index.ts` |
| All API/webhook calls | `frontend/src/services/api.ts` |
| Global state reducer | `frontend/src/context/AppContext.tsx` |
| n8n workflow (active) | `team_sync_dev_v2.1_with_JIRA.json` |
| Environment config | `frontend/.env` (create from CLAUDE.md template) |
| Tailwind config | `frontend/vite.config.ts` (Tailwind v4 Vite plugin) |

---

## Where to Add New Code

- **New UI page:** add component in `frontend/src/components/<feature>/`, add route in `App.tsx`
- **New API call:** add method to `TeamSyncAPI` in `frontend/src/services/api.ts`
- **New global state:** add action to `AppAction` union in `types/index.ts`, handle in `appReducer`
- **New n8n node/logic:** edit `team_sync_dev_v2.1_with_JIRA.json` — Code node JS goes in `jsCode` field (JSON-escaped)
- **New reusable component:** add to `frontend/src/components/ui/`

---

## Configuration Files

| File | Purpose |
|---|---|
| `frontend/vite.config.ts` | Vite build config + Tailwind CSS v4 plugin |
| `frontend/tsconfig.app.json` | TypeScript compiler config for src |
| `frontend/tsconfig.node.json` | TypeScript config for Vite config itself |
| `frontend/eslint.config.js` | ESLint flat config |
| `frontend/.gitignore` | Ignores `dist/`, `node_modules/`, `.env` |
