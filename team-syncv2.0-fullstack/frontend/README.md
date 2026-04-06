# TeamSync AI Frontend

A modern React frontend for the TeamSync PRD Automation System.

## Features

- **Chat Interface**: Conversational requirements gathering with Sam (AI Product Analyst)
- **PRD Viewer**: Markdown rendering with table of contents and quality scoring
- **Email Form**: Send PRD documents to recipients
- **JIRA Ticket Viewer**: View and approve JIRA ticket creation
- **Dashboard**: Overview of PRD history and system activity

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- React Router (routing)
- React Markdown (markdown rendering)
- Lucide React (icons)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
npm install
```

### Configuration

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env` with your n8n webhook URLs:

```env
VITE_N8N_BASE_URL=http://localhost:5678
VITE_CHAT_WEBHOOK_ID=unified-webhook-id
VITE_EMAIL_WEBHOOK_ID=d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f
VITE_JIRA_WEBHOOK_ID=jira-approval-form-webhook
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/
│   ├── ui/              # Reusable UI components
│   ├── chat/            # Chat interface
│   ├── prd/             # PRD viewer
│   ├── email/           # Email form
│   ├── jira/            # JIRA ticket viewer
│   ├── dashboard/       # Dashboard
│   └── layout/          # Layout components
├── context/             # React context
├── services/            # API services
├── types/               # TypeScript types
├── styles/              # Global styles
├── App.tsx
└── main.tsx
```

## Routes

- `/` - Chat interface (main entry point)
- `/dashboard` - Dashboard with PRD history
- `/prd` - View current PRD
- `/prd/:id` - View specific PRD by ID
- `/email` - Email form
- `/jira` - JIRA ticket viewer

## Integration with n8n

The frontend communicates directly with n8n webhooks:

1. **Chat messages** → `POST /webhook/{CHAT_WEBHOOK_ID}`
2. **Email form** → `POST /webhook/{EMAIL_WEBHOOK_ID}`
3. **JIRA approval** → `POST /webhook/{JIRA_WEBHOOK_ID}`

Data persistence is handled via localStorage for the demo.

## License

Internal use only.
