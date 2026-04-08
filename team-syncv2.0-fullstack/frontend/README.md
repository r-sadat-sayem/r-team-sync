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

For local Vite development, leave `VITE_API_URL` empty and let the dev server proxy
`/api` requests to the backend:

```env
VITE_API_URL=
VITE_API_PROXY_TARGET=http://localhost:8000
```

Set `VITE_API_URL` only when the frontend needs to call a backend on a different
origin directly.

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

## Authentication

The app now uses TeamSync account sign-up/login with an HTTP-only session cookie.
PRD history and active chat session state are namespaced per signed-in user in localStorage.
Google social login is also supported through backend-managed OAuth redirects.

## License

Internal use only.
