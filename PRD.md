# Product Requirements Document — TeamSync AI v2.0

**Project:** TeamSync AI  
**Version:** 2.0  
**Date:** 2026-04-09  
**Status:** Active Development (Phases 1–3 Complete)

---

## 1. Classification

```
Type:              Internal productivity tool / AI-assisted workflow
Priority:          High
Complexity:        High
Estimated Effort:  Completed — ongoing iteration
```

---

## 2. Product Overview

**Project Name:** TeamSync AI  
**Version:** 2.0  
**Introduction:**

TeamSync AI eliminates the manual work between "we have a product idea" and "tickets are in JIRA." A team member describes what they want to build in a conversational chat interface. An AI analyst (Sam) gathers requirements through a structured dialogue. When sufficient context is collected, a second AI persona (DevBridge) generates a complete, scored Product Requirements Document in one shot. The PRD is then emailed as a markdown attachment and — with a single approval — a full JIRA hierarchy (Epic → Stories → Subtasks) is created under the submitting user's own Atlassian identity.

The full cycle takes 5–10 minutes versus hours of manual writing and ticket filing.

---

## 3. Goals

**Primary Goal:**  
Automate the entire path from a raw product idea to a scored PRD and live JIRA tickets, reducing time-to-board from hours to under 10 minutes.

**User Experience Goal:**  
Make the tool feel like chatting with a knowledgeable colleague — not filling out a form. All actions (email, JIRA) happen inline without leaving the chat.

**Engineering Goal:**  
Replace the previous n8n-based workflow with a Python-native LangGraph pipeline that is testable, maintainable, and git-diffable. One deployable service instead of two.

**Quality Goal:**  
Every generated PRD receives a 0–100 quality score and letter grade so teams can immediately judge completeness without reading the full document.

---

## 4. Target Users

| Persona | Role | Use Case |
|---------|------|----------|
| Product Manager | Owns the product idea | Describes features, approves outline, receives PRD by email |
| Engineering Lead | Reviews technical requirements | Reviews PRD, approves JIRA creation |
| Developer | Executes tickets | Receives assigned JIRA subtasks from PRD |
| Team Lead | Manages delivery | Browses JIRA projects and boards from the app |

---

## 5. User Stories / Functional Requirements

### Authentication

**FR1:** As a new user, I can sign up with email and password so I have a personal account scoped to my sessions and PRDs.

**FR2:** As a returning user, I can log in with my Google account so I don't need to remember a separate password.

**FR3:** As an authenticated user, my session persists for 14 days across browser refreshes and server restarts so I don't lose my work.

### Requirements Gathering (Sam — AI Analyst)

**FR4:** As a user, I can describe a product idea in plain language and have Sam (AI analyst) ask me targeted follow-up questions to gather complete requirements, so I don't have to know the right format upfront.

**FR5:** As a user, I can upload supporting files (PDF, images, text, JSON) to provide context for my requirements, so Sam has all the information it needs.

**FR6:** As a user, I can type `/prd`, `/summary`, `/help`, or `/regenerate` as commands to control the conversation flow without having to phrase requests naturally.

**FR7:** As a user, I receive a structured PRD outline for approval before the full document is generated, so I can catch direction issues early and provide feedback.

### PRD Generation (DevBridge — AI Generator)

**FR8:** As a user, once I approve the outline, DevBridge generates a complete PRD covering: Classification, Product Overview, Goals, Functional Requirements (≥5), Non-Functional Requirements, Scope, Success Metrics, Design Considerations, Technical Considerations, and Timeline.

**FR9:** As a user, every generated PRD receives a quality score (0–100) and a letter grade (A–F) derived from section coverage, functional requirement count, test case count, and document length, so I immediately know if the PRD is complete.

**FR10:** As a user, I can download the generated PRD as a `.md` file directly from the chat so I have a portable copy.

**FR11:** As a user, I can run the JIRA command (`/jira`) or test-case command (`/testcases`) after PRD generation without re-doing the conversation, so I can trigger additional actions at any time.

### Email Delivery

**FR12:** As a user, I can send the generated PRD as an email attachment to any recipient directly from the chat using my connected Gmail account, so stakeholders receive a formatted copy without extra steps.

**FR13:** As a user who hasn't connected Gmail, I can still send PRDs via SMTP app password fallback, so email delivery works without OAuth setup.

### JIRA Integration

**FR14:** As a user, I can connect my Atlassian account via OAuth 2.0 from within the chat, so JIRA tickets are created under my identity and respect my board permissions.

**FR15:** As a user on a self-hosted or Data Center JIRA instance, I can authenticate with a Personal Access Token (PAT) instead of OAuth, so the tool works regardless of JIRA deployment type.

**FR16:** As a user, once JIRA is connected, the app automatically confirms ticket creation with a 5-second countdown that I can cancel, so common-path creation requires zero extra clicks.

**FR17:** As a user, I can approve JIRA ticket creation with an optional assignee email and reviewer notes, and the app creates a full Epic → Stories → Subtasks hierarchy extracted from the PRD's functional requirements and test cases.

**FR18:** As a user, the assignee receives a notification email listing all created tickets with direct JIRA links, so they're immediately aware of the new work.

**FR19:** As a user, I can browse all my JIRA projects and their boards from the Projects page, and click through to open any board directly in JIRA.

**FR20:** As a user, I can create JIRA tickets from any existing PRD markdown directly from the Projects page without going through the chat flow.

### Session & History Management

**FR21:** As a user, I can have multiple concurrent chat sessions open in separate tabs and switch between them without losing state, so I can work on multiple PRDs simultaneously.

**FR22:** As a user, I can view a history of all my generated PRDs with quality scores and grades, search by title or filename, and restore any past session to continue the conversation.

**FR23:** As a user, a dashboard shows me my total PRD count, average quality score, number of JIRA tickets created, and recent activity, so I can track my usage at a glance.

**FR24:** As a user, my session state (conversation, PRD, JIRA results) is durable across browser refreshes, tab closes, and server restarts via PostgreSQL-backed LangGraph checkpoints.

### Test Case Generation

**FR25:** As a user, I can request test case generation after PRD creation, and receive a structured set of ≥10 happy-path test cases and ≥5 edge-case test cases derived from the functional requirements.

---

## 6. Non-Functional Requirements

**Performance:**
- PRD generation streams tokens in real time via SSE; first token must appear within 3 seconds of request.
- JIRA ticket creation (Epic + 5 Stories) must complete within 30 seconds under normal network conditions.
- The chat interface must remain responsive while the SSE stream is active.

**Security:**
- Session tokens are stored as hashes in PostgreSQL; raw tokens are never persisted.
- Session cookies are HttpOnly, preventing JavaScript access.
- OAuth tokens (Gmail, JIRA, Google login) are stored per-user in the database; never returned to the frontend.
- All API routes require an authenticated session; unauthenticated requests return 401.
- Session ownership is enforced — users can only access their own sessions and PRDs.

**Reliability:**
- JIRA `create_issue` retries up to 3 times on network/timeout errors with exponential backoff (0.5s, 1.0s) to survive transient connection drops mid-hierarchy.
- Gmail token is refreshed before each send; falls back to existing token if refresh fails.
- LangGraph state persists to PostgreSQL at every node transition; no state is lost on server restart.

**Usability:**
- All actions (email, JIRA connect, ticket creation) happen inline in the chat without page navigation.
- HTTP API calls are logged to the browser console (collapsible groups with request/response bodies) for developer debugging.
- Console logging can be disabled via `VITE_HTTP_LOG=false` in the frontend environment.

**Scalability:**
- Single-user internal tool; no horizontal scaling requirement in v2.0.
- LangGraph runs in-process within FastAPI — no separate worker process or queue.

---

## 7. Scope

**In Scope (v2.0):**
- Conversational requirements gathering via Sam (Claude via Rakuten AI Gateway)
- PRD outline approval with feedback loop
- Full PRD generation via DevBridge with quality scoring
- PRD download as `.md` file
- Gmail OAuth + SMTP fallback for email delivery
- JIRA OAuth 2.0 + PAT for ticket creation
- Epic → Stories → Subtasks hierarchy extracted from PRD
- Multi-tab concurrent chat sessions
- PRD history with search and session restore
- JIRA projects and boards browser
- File upload for requirements context (PDF, images, text)
- Test case generation from PRD
- User authentication (email/password + Google OAuth)
- Dashboard with usage statistics
- Browser console HTTP logging for development

**Out of Scope (v2.0):**
- Confluence export / publishing
- Slack / Teams notifications
- Multi-user collaboration on a single PRD
- JIRA webhook sync for ticket status updates
- RAG over past PRDs
- Rate limiting (internal tool, small team)
- CI/CD pipeline configuration
- Mobile-responsive design (desktop-first)

---

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Time from first message to scored PRD | < 10 minutes |
| PRD quality score on first generation | ≥ 70 (grade C or above) |
| JIRA ticket creation success rate | ≥ 95% of approved sessions |
| Session state durability | 100% — no state lost on server restart |
| Email delivery success rate | ≥ 99% (with SMTP fallback) |

---

## 9. Technical Architecture

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS v3, React Router 7 |
| Backend | Python 3.12, FastAPI, uvicorn |
| AI Workflow | LangGraph (StateGraph + HITL interrupts + PostgreSQL checkpointer) |
| LLM | Claude (claude-haiku-4-5 / claude-3-7-sonnet) via Rakuten AI Gateway |
| Database | PostgreSQL 15 (LangGraph checkpoints + app schema) |
| Email | Gmail API (OAuth 2.0) + SMTP fallback |
| JIRA | REST API v3 via httpx (OAuth 2.0 + PAT) |
| Auth | Cookie-based sessions (SHA-256 token hash) + Google OAuth |
| Deployment | Docker Compose (3 services: postgres, backend, frontend) |

### LangGraph Workflow

```
START → route_entry()
  │
  ├─ analyze (Sam: requirements gathering)
  │     │ GENERATE_PRD: signal detected → mode = "generate"
  │     └─ route_after_analyze → generate_prd_outline
  │
  ├─ generate_prd_outline → prd_outline_interrupt (HITL: approve/revise)
  │     ├─ [approve] → generate_prd
  │     └─ [revise]  → analyze (feedback loop)
  │
  ├─ generate_prd → validate → post_prd_interrupt (HITL: choose action)
  │     ├─ [email]       → email_interrupt → send_email → post_prd_interrupt
  │     ├─ [test_cases]  → generate_test_cases → validate_test_cases → post_prd_interrupt
  │     ├─ [jira]        → jira_interrupt → route_after_jira
  │     │                      └─ [approve] → create_jira → END
  │     └─ [done]        → END
  │
  └─ Direct commands (when PRD exists):
        /jira        → jira_interrupt
        /testcases   → generate_test_cases
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `users` | User accounts (email, password hash, display name) |
| `auth_sessions` | Session tokens (hashed, with expiry) |
| `app_sessions` | Maps LangGraph thread_id to user_id |
| `oauth_connections` | OAuth tokens per user per provider (gmail, jira) |

### SSE Event Contract

| Event Type | Frontend Action |
|------------|----------------|
| `token` | Append to active message bubble |
| `status` | Show transient progress label |
| `prd_complete` | Render quality badge, enable download |
| `prd_outline_form` | Render inline approval form |
| `post_prd_actions` | Render action menu |
| `email_sent` | Show confirmation banner |
| `interrupt` | Render inline HITL form (email/jira/outline) |
| `jira_progress` | Update status label with "Creating story N of M" |
| `jira_created` | Render Epic + Story links |
| `notification_sent` | Show "notification sent to {email}" |
| `turn_end` | Re-enable input, hide spinner |
| `error` | Show error toast |

---

## 10. Constraints and Assumptions

- LLM access is through the Rakuten AI Gateway; direct Anthropic API is not used.
- JIRA ticket type names (Epic, Story, Subtask) are configurable per deployment and may vary between JIRA Cloud and Server instances.
- Gmail OAuth requires a verified Google Cloud project with the `gmail.send` scope approved.
- The PRD outline approval interrupt is the first HITL gate; it fires after Sam detects the `GENERATE_PRD:` signal and before full PRD generation begins.
- All OAuth callback URLs are environment-specific and must be registered in the respective provider's app settings.

---

## 11. Future Roadmap

### Near-Term
- Confluence export (publish PRD as a page via Atlassian REST API)
- Slack/Teams notification when PRD + JIRA are complete
- CSRF nonce in OAuth state parameter for improved security

### Medium-Term
- RAG over past PRDs so Sam references similar past projects during requirements gathering
- Multi-product / multi-board routing at the JIRA approval step
- JIRA webhook sync to surface ticket status updates in chat history

### Long-Term
- LangGraph multi-agent architecture (Sam and DevBridge as separate agents with supervisor)
- Streaming PRD into a collaborative editing surface (Notion, Confluence block editor)
- SSO via Atlassian OAuth for app authentication (eliminating separate credentials)
- Retire n8n v1 entirely once v2.0 is fully validated in production
