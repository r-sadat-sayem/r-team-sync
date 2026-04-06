# TeamSync PRD Automation System - Backend Plan

## Executive Summary

This document outlines the plan to replicate the n8n PRD Automation System as a fullstack Node.js/Express application with PostgreSQL database, OpenAI/Claude AI integration, and JIRA API integration.

## System Overview

The original n8n system consists of:
1. **Conversational AI Agent (Sam)** - Gathers requirements through chat
2. **PRD Generator (DevBridge)** - Creates comprehensive PRD documents
3. **Quality Validator** - Scores PRD output (0-100)
4. **Email Delivery** - Sends PRD via Gmail
5. **JIRA Integration** - Creates Epic → Task → Subtask hierarchy

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FULLSTACK APPLICATION                      │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React/Vue)          Backend (Node.js/Express)         │
│  ┌─────────────────┐           ┌──────────────────────────────┐   │
│  │ Chat Interface  │◄─────────►│  API Routes                │   │
│  │ - WebSocket     │           │  /api/chat                 │   │
│  │ - Message UI    │           │  /api/sessions             │   │
│  └─────────────────┘           │  /api/prd                  │   │
│                                │  /api/jira                 │   │
│                                │  /api/email                │   │
│                                └────────────┬───────────────┘   │
│                                             │                    │
│                                ┌────────────▼───────────────┐     │
│                                │    Services Layer        │     │
│                                │  - ChatService           │     │
│                                │  - PRDService            │     │
│                                │  - JIRAService           │     │
│                                │  - EmailService          │     │
│                                │  - AIService             │     │
│                                └────────────┬───────────────┘     │
│                                             │                      │
│                     ┌───────────────────────┼──────────────────┐ │
│                     ▼                       ▼                  ▼ │
│              ┌──────────┐          ┌─────────────┐    ┌────────┐│
│              │PostgreSQL│          │OpenAI/Claude│    │ JIRA   ││
│              └──────────┘          └─────────────┘    └────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema (PostgreSQL)

```sql
-- Sessions table for conversation continuity
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key VARCHAR(255) UNIQUE NOT NULL,
    mode VARCHAR(50) DEFAULT 'analyze', -- 'analyze', 'generate', 'complete'
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'paused', 'completed'
    context_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table for conversation history
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    action VARCHAR(50), -- 'continue', 'generate', 'done'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PRD Documents table
CREATE TABLE prd_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    markdown_content TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    quality_score INTEGER,
    grade VARCHAR(5),
    test_case_count INTEGER,
    sections_detected JSONB,
    missing_sections JSONB,
    status VARCHAR(50) DEFAULT 'generated', -- 'generated', 'emailed', 'jira_created'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email deliveries table
CREATE TABLE email_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prd_id UUID REFERENCES prd_documents(id) ON DELETE CASCADE,
    recipient_name VARCHAR(255),
    recipient_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'sent', 'failed'
    sent_at TIMESTAMP,
    error_message TEXT
);

-- JIRA tickets table
CREATE TABLE jira_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prd_id UUID REFERENCES prd_documents(id) ON DELETE CASCADE,
    epic_key VARCHAR(50),
    epic_title VARCHAR(500),
    task_key VARCHAR(50),
    task_title VARCHAR(500),
    subtask_key VARCHAR(50),
    subtask_title VARCHAR(500),
    project_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'created', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_prd_session_id ON prd_documents(session_id);
CREATE INDEX idx_sessions_key ON sessions(session_key);
```

## API Structure

### 1. Chat Endpoints

```javascript
// POST /api/chat/message
// Send a message to the AI agent
{
  "sessionId": "uuid-or-generate-new",
  "message": "I want to build a mobile expense tracking app..."
}

// Response
{
  "sessionId": "uuid",
  "response": "That sounds interesting! ...",
  "action": "continue", // or "generate" or "done"
  "mode": "analyze",    // or "generate"
  "contextSummary": "..." // only when action=generate
}

// GET /api/chat/:sessionId/history
// Get conversation history

// POST /api/chat/:sessionId/reset
// Reset/clear session
```

### 2. Session Endpoints

```javascript
// POST /api/sessions
// Create new session

// GET /api/sessions/:id
// Get session details

// DELETE /api/sessions/:id
// Delete session and all related data
```

### 3. PRD Endpoints

```javascript
// POST /api/prd/generate
// Trigger PRD generation (after user confirms)
{
  "sessionId": "uuid",
  "contextSummary": "..."
}

// GET /api/prd/:id
// Get PRD document

// GET /api/prd/:id/download
// Download PRD as markdown file

// POST /api/prd/:id/validate
// Re-validate PRD quality
```

### 4. Email Endpoints

```javascript
// POST /api/email/send
// Send PRD via email
{
  "prdId": "uuid",
  "recipientName": "John Doe",
  "recipientEmail": "john@example.com"
}
```

### 5. JIRA Endpoints

```javascript
// POST /api/jira/extract
// Extract JIRA content from PRD
{
  "prdId": "uuid"
}

// POST /api/jira/create
// Create JIRA tickets (after approval)
{
  "prdId": "uuid",
  "approval": "APPROVE"
}

// GET /api/jira/:prdId/status
// Get JIRA ticket status
```

## Service Layer Design

### 1. AIService

```javascript
class AIService {
  // Initialize with OpenAI/Claude API
  constructor(apiKey, model = 'gpt-4') {}
  
  // Generate response for requirements gathering
  async chatAnalyze(sessionHistory, userMessage) {}
  
  // Generate complete PRD document
  async generatePRD(contextSummary) {}
  
  // Parse agent response for signals
  parseResponse(response) {
    // Detect GENERATE_PRD: signal
    // Detect action type (continue/generate/done)
    // Extract context summary
  }
}
```

### 2. ChatService

```javascript
class ChatService {
  constructor(aiService, db) {}
  
  // Process incoming message
  async processMessage(sessionId, message) {
    // 1. Get session history
    // 2. Build system prompt based on mode
    // 3. Call AI service
    // 4. Parse response
    // 5. Save message
    // 6. Return formatted response
  }
  
  // Build dynamic system prompt
  buildSystemPrompt(mode, contextSummary) {
    // Returns Sam (analyze) or DevBridge (generate) prompt
  }
}
```

### 3. PRDService

```javascript
class PRDService {
  constructor(db) {}
  
  // Validate PRD quality
  validatePRD(markdown) {
    // Check for 8 required sections
    // Count test cases (TC001, TC002...)
    // Calculate score 0-100
    // Return grade A-F
  }
  
  // Generate filename from content
  generateFilename(markdown) {}
  
  // Convert to binary for email attachment
  convertToBinary(markdown, filename) {}
}
```

### 4. JIRAService

```javascript
class JIRAService {
  constructor(jiraConfig) {}
  
  // Extract content from PRD markdown
  extractContent(markdown) {
    // epicTitle from **Project Name**
    // epicDescription from Product Overview
    // tasks[] from FR1, FR2...
    // subtasks[] from TC001, TC002...
  }
  
  // Create Epic
  async createEpic(projectId, title, description) {}
  
  // Create Task (child of Epic)
  async createTask(projectId, epicKey, title) {}
  
  // Create Subtask (child of Task, assigned to agent)
  async createSubtask(projectId, taskKey, title, assignee) {}
}
```

### 5. EmailService

```javascript
class EmailService {
  constructor(smtpConfig) {}
  
  // Send PRD as email attachment
  async sendPRD(recipientEmail, recipientName, prdMarkdown, filename) {
    // Create email with markdown attachment
    // Return success/failure
  }
}
```

## System Prompts

### Sam - AI Product Analyst (Analyze Mode)

```
You are Sam, an Expert AI Product Analyst. Your role is to gather specific requirements through conversation.

CRITICAL: When you have gathered sufficient information, you MUST respond EXACTLY in this format (no extra text):

GENERATE_PRD:
- Project: [exact project name]
- Type: [Feature/Bug/Enhancement]
- Platform: [specific platform]
- Key Features: [list 3-5]
- Target Users: [specific demographics]
- Timeline: [deadline]
- Success Metric: [measurable goal]

Shall I proceed with generating the complete PRD document?

Ask max 3 questions at a time. Avoid placeholders like "MyApp".
```

### DevBridge - PRD Generator (Generate Mode)

```
You are DevBridge, an elite AI PRD Generator.

## CONTEXT PROVIDED:
{contextSummary}

## CRITICAL: Generate the COMPLETE PRD document NOW in ONE response.

Structure:
# Classification Summary
```
Type: [from context]
Priority: [Critical/High/Medium/Low]
Complexity: [Low/Medium/High]
Estimated Effort: [X Story Points]
```

# Product Overview
- **Project Name**: [from context]
- **Feature Name**: [from context]
- **Version**: 1.0
- **Date**: {currentDate}
- **Project Owner**: [from context or TBD]
- **Introduction**: [brief overview]

# Goals
- Primary Goal: [from context]
- User Experience Goal: [derived]
- Project Goal Alignment: [related]

# User Stories / Functional Requirements
[3-5 user stories]
**FR1**: [feature 1]
**FR2**: [feature 2]

# Non-Functional Requirements
- Performance: [expectations]
- Security: [requirements]
- Usability: [standards]

# Scope (In/Out)
**In Scope:**
- [features from context]

**Out of Scope:**
- [exclusions]

# Success Metrics
- [metrics from context with targets]

# Design and UX Considerations
- Layout: [based on platform]
- User Flows: [workflows]

# Technical Considerations
- Platform: [from context]
- Technology Stack: [appropriate choices]
- Dependencies: [APIs mentioned]

# Timeline and Key Milestones
- Week 1-2: [phases]

# Stakeholders
- Project Owner: [from context]
- Development Team: [roles]

# Jira Ticket Templates

**Epic:**
```
Issue Type: Epic
Summary: [project objective]
Description: [context]
Acceptance Criteria: [conditions]
```

**Stories:**
```
Story 1: [feature]
Acceptance Criteria: [specific tests]
```

# Test Case Scenarios

## Happy Path Tests

**TC001: [Core Feature Test]**
- Description: [primary workflow]
- Steps: 1. [action] 2. [action]
- Expected: [result]
- Priority: Critical

**TC002-TC010**: [9 more tests]

## Edge Cases

**TC101: [Boundary Test]**
- Description: [edge condition]
- Steps: [trigger]
- Expected: [error handling]

**TC102-TC105**: [4 more edge tests]

Rules:
- Use ONLY context details
- Write TBD if missing
- Minimum 15 test cases
- Professional markdown
```

## Implementation Phases

### Phase 1: Core Infrastructure
1. Set up Express server with TypeScript
2. Configure PostgreSQL with migrations
3. Set up environment configuration
4. Create database models

### Phase 2: Chat & AI Integration
1. Implement AIService with OpenAI/Claude
2. Create ChatService with session management
3. Build system prompt builder
4. Implement response parser
5. Add WebSocket support for real-time chat

### Phase 3: PRD Generation
1. Implement PRDService with validation
2. Create quality scoring algorithm
3. Add document filename generation
4. Implement binary conversion

### Phase 4: Email Integration
1. Set up EmailService with Nodemailer
2. Create email templates
3. Implement attachment handling
4. Add delivery tracking

### Phase 5: JIRA Integration
1. Implement JIRAService with API client
2. Create content extraction from PRD
3. Build Epic → Task → Subtask creation flow
4. Add approval workflow (HITL)

### Phase 6: Frontend
1. Create React chat interface
2. Build PRD viewer component
3. Add email form UI
4. Create JIRA approval UI

## Environment Variables

```bash
# Server
PORT=3000
NODE_ENV=development

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/teamsync

# AI Provider (OpenAI or Claude)
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Or for Claude
# AI_PROVIDER=claude
# CLAUDE_API_KEY=sk-ant-...
# CLAUDE_MODEL=claude-3-opus-20240229

# JIRA
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=user@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_ID=10033
JIRA_ASSIGNEE_ID=712020:819804e5-2d30-4b3d-9388-7f8dfb416842

# Email (Gmail SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

## Project Structure

```
teamsync-backend/
├── src/
│   ├── config/
│   │   ├── database.ts
│   │   ├── env.ts
│   │   └── prompts.ts          # System prompts
│   ├── controllers/
│   │   ├── chatController.ts
│   │   ├── prdController.ts
│   │   ├── jiraController.ts
│   │   └── emailController.ts
│   ├── services/
│   │   ├── AIService.ts
│   │   ├── ChatService.ts
│   │   ├── PRDService.ts
│   │   ├── JIRAService.ts
│   │   └── EmailService.ts
│   ├── models/
│   │   ├── Session.ts
│   │   ├── Message.ts
│   │   ├── PRDDocument.ts
│   │   ├── EmailDelivery.ts
│   │   └── JIRATicket.ts
│   ├── routes/
│   │   ├── chat.ts
│   │   ├── sessions.ts
│   │   ├── prd.ts
│   │   ├── jira.ts
│   │   └── email.ts
│   ├── middleware/
│   │   ├── errorHandler.ts
│   │   └── validateRequest.ts
│   ├── types/
│   │   └── index.ts
│   └── app.ts
├── migrations/
│   └── 001_initial.sql
├── tests/
├── package.json
├── tsconfig.json
└── .env.example
```

## Key Implementation Notes

1. **Session Management**: Use UUID-based sessions stored in PostgreSQL with 20-message context window (configurable)

2. **AI Response Parsing**: Implement robust regex patterns to detect:
   - `GENERATE_PRD:` signal with structured context
   - Placeholder rejection (MyApp, Example Project, etc.)
   - User confirmation patterns (yes, proceed, ok, etc.)

3. **Quality Scoring**: Implement the same algorithm as n8n:
   - 50 points for 8 required sections
   - 30 points for test cases (15+ = 30, 10+ = 25, 5+ = 15)
   - 20 points for length (>5000 = 20, >3000 = 10, >2000 = 5)

4. **JIRA Hierarchy**: Create exactly one Epic → one Task → one Subtask per run (matching n8n POC scope)

5. **Human-in-the-Loop**: Implement wait/approval pattern for:
   - Email recipient collection (form)
   - JIRA ticket creation approval

## Next Steps

1. Review and approve this plan
2. Initialize the Node.js project with TypeScript
3. Set up PostgreSQL database and migrations
4. Implement services layer (AI, Chat, PRD)
5. Build API routes and controllers
6. Create frontend interface
7. Integrate JIRA and Email services
8. Test end-to-end flow

## Estimated Timeline

- Phase 1-2 (Core + Chat): 2-3 days
- Phase 3 (PRD): 1-2 days
- Phase 4-5 (Email + JIRA): 2-3 days
- Phase 6 (Frontend): 2-3 days
- Testing & Polish: 1-2 days

**Total: 8-13 days for MVP**
