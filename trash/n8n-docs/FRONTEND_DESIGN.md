# TeamSync AI Frontend Design Document

## Overview

A modern React frontend for the TeamSync PRD Automation System that provides a seamless interface for:
- Conversational AI requirements gathering with "Sam" (AI Product Analyst)
- PRD document viewing with markdown rendering
- Email delivery form for PRD distribution
- JIRA ticket status viewer
- Dashboard for PRD history

## Tech Stack

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (built on Radix UI)
- **State Management**: React Context + useReducer for global state
- **Routing**: React Router v6
- **Markdown Rendering**: react-markdown with remark-gfm
- **HTTP Client**: Native fetch with custom hooks
- **Icons**: Lucide React

## Architecture

### Component Hierarchy

```
App
├── Layout
│   ├── Sidebar (Navigation)
│   ├── Header (User actions, notifications)
│   └── Main Content Area
│       ├── Routes:
│       │   ├── /chat → ChatInterface
│       │   ├── /prd/:id → PRDViewer
│       │   ├── /email → EmailForm
│       │   ├── /jira → JIRATicketViewer
│       │   └── /dashboard → Dashboard
│       └── Shared Components:
│           ├── ChatMessage
│           ├── PRDPreview
│           ├── QualityScoreBadge
│           └── StatusIndicator
```

### State Management

```typescript
// Global State Structure
interface AppState {
  // Session
  sessionId: string | null;
  currentMode: 'analyze' | 'generate' | 'complete';
  
  // Chat
  messages: Message[];
  isTyping: boolean;
  
  // PRD
  currentPRD: PRDDocument | null;
  prdHistory: PRDDocument[];
  
  // Email
  emailStatus: 'idle' | 'sending' | 'sent' | 'error';
  
  // JIRA
  jiraTickets: JIRATicket[];
  jiraApprovalStatus: 'pending' | 'approved' | 'rejected';
}
```

## Page Designs

### 1. Chat Interface (`/chat`)

**Purpose**: Primary interaction point for requirements gathering with Sam

**Layout**:
- Full-height chat container with message history
- Input area at bottom with send button
- Typing indicator when AI is responding
- Session persistence via localStorage

**Features**:
- Real-time message streaming (WebSocket or polling)
- Message bubbles with timestamps
- File upload support (for context documents)
- "Generate PRD" button appears when requirements are complete
- Quality score display after PRD generation

**Components**:
```typescript
interface ChatInterfaceProps {
  sessionId: string;
  onPRDGenerated: (prd: PRDDocument) => void;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    action?: 'generate' | 'done' | 'continue';
    qualityScore?: number;
  };
}
```

### 2. PRD Viewer (`/prd/:id`)

**Purpose**: Display generated PRD documents with markdown rendering

**Layout**:
- Two-column layout on desktop: Table of Contents (left) + Content (right)
- Single column on mobile with collapsible TOC
- Toolbar with download, copy, and email actions

**Features**:
- Syntax-highlighted code blocks
- Collapsible sections
- Search within document
- Export to PDF/Markdown
- Quality score badge
- Version history sidebar

**Components**:
```typescript
interface PRDViewerProps {
  prdId: string;
}

interface PRDDocument {
  id: string;
  title: string;
  content: string; // Markdown
  qualityScore: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  createdAt: Date;
  sections: PRDSection[];
  testCaseCount: number;
}

interface PRDSection {
  id: string;
  title: string;
  level: number;
  content: string;
}
```

### 3. Email Form (`/email`)

**Purpose**: Collect recipient information and send PRD via email

**Layout**:
- Centered card layout
- Form fields: Name, Email
- PRD preview thumbnail
- Send button with loading state

**Features**:
- Email validation
- Success/error notifications
- Multiple recipient support (future)
- Template selection (future)

**Components**:
```typescript
interface EmailFormProps {
  prdId: string;
  onSent: () => void;
}

interface EmailFormData {
  recipientName: string;
  recipientEmail: string;
  prdId: string;
}
```

### 4. JIRA Ticket Viewer (`/jira`)

**Purpose**: Display and manage JIRA tickets created from PRDs

**Layout**:
- Kanban-style board or list view
- Ticket cards with status indicators
- Approval workflow UI
- Epic/Task/Subtask hierarchy visualization

**Features**:
- Real-time ticket status updates
- Approval form for ticket creation
- Link to JIRA instance
- Ticket details modal
- Bulk actions (future)

**Components**:
```typescript
interface JIRATicketViewerProps {
  prdId?: string;
}

interface JIRATicket {
  id: string;
  key: string;
  type: 'Epic' | 'Task' | 'Subtask';
  summary: string;
  description: string;
  status: 'To Do' | 'In Progress' | 'Done';
  assignee?: string;
  parentKey?: string;
  epicTitle?: string;
}

interface JIRAApprovalForm {
  decision: 'APPROVE' | 'REJECT';
  notes: string;
}
```

### 5. Dashboard (`/dashboard`)

**Purpose**: Overview of all PRDs and system activity

**Layout**:
- Stats cards at top (Total PRDs, Avg Quality, etc.)
- Recent PRDs list
- Activity timeline
- Quick actions

**Features**:
- PRD history with search and filters
- Quality score trends
- Export all data
- Session management

**Components**:
```typescript
interface DashboardProps {}

interface DashboardStats {
  totalPRDs: number;
  averageQualityScore: number;
  totalJIRATickets: number;
  recentActivity: ActivityItem[];
}

interface ActivityItem {
  id: string;
  type: 'prd_created' | 'email_sent' | 'jira_ticket_created';
  description: string;
  timestamp: Date;
  metadata: Record<string, any>;
}
```

## API Integration

### n8n Webhook Endpoints

```typescript
// Chat message endpoint
POST /webhook/unified-webhook-id
{
  chatInput: string;
  sessionId: string;
  mode: 'analyze' | 'generate';
}

// Email form submission
POST /webhook/d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f
{
  Name: string;
  Email: string;
}

// JIRA approval
POST /webhook/jira-approval-form-webhook
{
  Decision: 'APPROVE' | 'REJECT';
  Notes: string;
}
```

### Custom API Layer

```typescript
// services/api.ts
class TeamSyncAPI {
  async sendMessage(input: string, sessionId: string): Promise<AgentResponse>;
  async getPRDHistory(): Promise<PRDDocument[]>;
  async getPRDById(id: string): Promise<PRDDocument>;
  async submitEmailForm(data: EmailFormData): Promise<void>;
  async submitJIRAApproval(data: JIRAApprovalForm): Promise<void>;
  async getJIRATickets(prdId?: string): Promise<JIRATicket[]>;
}
```

## Design System

### Colors

```css
/* Primary */
--primary: #6366f1;      /* Indigo 500 */
--primary-light: #818cf8; /* Indigo 400 */
--primary-dark: #4f46e5;  /* Indigo 600 */

/* Background */
--bg-primary: #0f1117;    /* Dark background */
--bg-secondary: #1a1d24;  /* Card background */
--bg-tertiary: #252a33;   /* Elevated surfaces */

/* Text */
--text-primary: #e2e8f0;   /* Slate 200 */
--text-secondary: #94a3b8; /* Slate 400 */
--text-muted: #64748b;     /* Slate 500 */

/* Status */
--success: #34d399;  /* Emerald 400 */
--warning: #fbbf24;  /* Amber 400 */
--error: #f87171;    /* Red 400 */
--info: #60a5fa;     /* Blue 400 */

/* Quality Scores */
--grade-a: #34d399;  /* 90-100 */
--grade-b: #60a5fa;  /* 80-89 */
--grade-c: #fbbf24;  /* 70-79 */
--grade-d: #fb923c;  /* 60-69 */
--grade-f: #f87171;  /* <60 */
```

### Typography

- **Headings**: Inter, sans-serif, font-weight 700
- **Body**: Inter, sans-serif, font-weight 400
- **Code**: JetBrains Mono, monospace

### Spacing

- Base unit: 4px
- Scale: 4, 8, 12, 16, 24, 32, 48, 64, 96

### Border Radius

- Small: 6px (buttons, inputs)
- Medium: 10px (cards)
- Large: 16px (modals)
- Full: 9999px (pills, avatars)

## Responsive Breakpoints

```css
/* Mobile first approach */
sm: 640px;   /* Small tablets */
md: 768px;   /* Tablets */
lg: 1024px;  /* Small laptops */
xl: 1280px;  /* Desktops */
2xl: 1536px; /* Large screens */
```

## File Structure

```
src/
├── components/
│   ├── ui/                    # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── dialog.tsx
│   │   └── ...
│   ├── chat/
│   │   ├── ChatInterface.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   └── TypingIndicator.tsx
│   ├── prd/
│   │   ├── PRDViewer.tsx
│   │   ├── PRDPreview.tsx
│   │   ├── TableOfContents.tsx
│   │   └── QualityScoreBadge.tsx
│   ├── email/
│   │   ├── EmailForm.tsx
│   │   └── EmailSuccess.tsx
│   ├── jira/
│   │   ├── JIRATicketViewer.tsx
│   │   ├── TicketCard.tsx
│   │   ├── ApprovalForm.tsx
│   │   └── StatusIndicator.tsx
│   ├── dashboard/
│   │   ├── Dashboard.tsx
│   │   ├── StatsCard.tsx
│   │   ├── PRDList.tsx
│   │   └── ActivityTimeline.tsx
│   └── layout/
│       ├── Layout.tsx
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       └── Navigation.tsx
├── hooks/
│   ├── useChat.ts
│   ├── usePRD.ts
│   ├── useJIRA.ts
│   └── useLocalStorage.ts
├── context/
│   └── AppContext.tsx
├── services/
│   ├── api.ts
│   ├── n8nClient.ts
│   └── storage.ts
├── types/
│   ├── index.ts
│   ├── chat.ts
│   ├── prd.ts
│   ├── jira.ts
│   └── api.ts
├── utils/
│   ├── formatters.ts
│   ├── validators.ts
│   └── markdown.ts
├── styles/
│   └── globals.css
├── App.tsx
├── main.tsx
└── router.tsx
```

## Implementation Phases

### Phase 1: Core Setup
- [ ] Initialize Vite project with TypeScript
- [ ] Configure Tailwind CSS
- [ ] Set up shadcn/ui
- [ ] Create base layout components
- [ ] Set up routing

### Phase 2: Chat Interface
- [ ] Build chat UI components
- [ ] Implement message state management
- [ ] Connect to n8n webhook
- [ ] Add typing indicators
- [ ] Session persistence

### Phase 3: PRD Viewer
- [ ] Markdown rendering setup
- [ ] Table of Contents generation
- [ ] Syntax highlighting
- [ ] Quality score display
- [ ] Download functionality

### Phase 4: Email & JIRA
- [ ] Email form with validation
- [ ] JIRA ticket viewer
- [ ] Approval workflow UI
- [ ] Status indicators

### Phase 5: Dashboard
- [ ] Stats overview
- [ ] PRD history list
- [ ] Activity timeline
- [ ] Search and filters

### Phase 6: Polish
- [ ] Animations and transitions
- [ ] Error handling
- [ ] Loading states
- [ ] Responsive refinements
- [ ] Accessibility audit

## Environment Variables

```bash
# .env
VITE_N8N_BASE_URL=http://localhost:5678
VITE_CHAT_WEBHOOK_ID=unified-webhook-id
VITE_EMAIL_WEBHOOK_ID=d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f
VITE_JIRA_WEBHOOK_ID=jira-approval-form-webhook
VITE_JIRA_BASE_URL=https://your-domain.atlassian.net
```

## Notes

- The frontend will communicate directly with n8n webhooks
- Session persistence via localStorage for demo purposes
- No backend required - all logic lives in n8n workflows
- Consider implementing a simple proxy if CORS issues arise
- JIRA API calls should be handled through n8n, not directly from frontend
