# TeamSync AI — API Reference

Base URL: `http://localhost:8000` (dev) | `https://your-domain.com` (prod)

All `/api/v1/*` endpoints require: `X-API-Key: <BACKEND_API_KEY>`

Full interactive docs: `{BASE_URL}/docs` (Swagger UI) | `{BASE_URL}/redoc` (ReDoc)

---

## Health

### `GET /health`
Liveness probe. No auth required.
```json
{ "status": "ok", "timestamp": "2026-04-03T12:00:00Z" }
```

### `GET /api/v1/status`
Readiness probe — checks all dependencies.
```json
{
  "status": "ready",
  "components": {
    "database": "ok",
    "n8n": "ok",
    "ollama": "ok"
  }
}
```

---

## Chat

### `POST /api/v1/chat`
Proxy a user message to the n8n chat webhook. Returns the agent's response.

**Request:**
```json
{
  "message": "I want to build a mobile expense tracker",
  "session_id": "session-uuid-optional"   // omit for new session
}
```

**Response:**
```json
{
  "output": "Great! Let me ask a few questions...",
  "session_id": "abc-123",
  "action": "continue",
  "mode": "analyze"
}
```

`action` values: `continue` (still gathering) | `generate` (building PRD) | `done` (PRD ready)

---

## Sessions

### `GET /api/v1/sessions`
List chat sessions for the current API key.

Query params: `page=1`, `per_page=20`

**Response:**
```json
{
  "items": [
    {
      "id": "abc-123",
      "created_at": "2026-04-03T10:00:00Z",
      "message_count": 8,
      "prd_id": "prd-456"   // null if PRD not yet generated
    }
  ],
  "total": 1,
  "page": 1
}
```

### `GET /api/v1/sessions/{session_id}`
Get session detail including message history.

---

## PRD

### `POST /api/v1/prd`
Store a completed PRD. Called by n8n after generation. Requires `X-API-Key`.

**Request:**
```json
{
  "session_id": "abc-123",
  "title": "Mobile Expense Tracker",
  "content": "# Classification Summary\n...",
  "quality_score": 87,
  "grade": "B",
  "file_name": "mobile_expense_tracker_2026-04-03.md"
}
```

**Response:** `201 Created`
```json
{ "id": "prd-456", "created_at": "2026-04-03T10:05:00Z" }
```

### `GET /api/v1/prd`
List PRDs. Query params: `page`, `per_page`, `session_id`

### `GET /api/v1/prd/{prd_id}`
Get PRD by ID. Returns full markdown content.

### `DELETE /api/v1/prd/{prd_id}`
Soft-delete a PRD.

---

## JIRA

### `POST /api/v1/jira/approve`
Trigger JIRA ticket creation by resuming the n8n Wait node.

**Request:**
```json
{
  "session_id": "abc-123",
  "decision": "APPROVE",
  "notes": "Looks good, proceed"
}
```

### `GET /api/v1/jira/tickets`
List JIRA tickets created from PRDs.
Query params: `session_id`, `page`, `per_page`

---

## AI Gateway (Phase 5 — stub)

### `POST /api/v1/ai/query`
Route an AI query to the configured provider (Ollama, Rakuten, OpenAI).

**Request:**
```json
{
  "prompt": "Summarize this PRD: ...",
  "provider": "rakuten",   // optional, overrides AI_PROVIDER env var
  "model": "rakuten-model-id"
}
```

**Response:**
```json
{
  "output": "This PRD describes...",
  "provider": "rakuten",
  "model": "rakuten-model-id",
  "tokens_used": 312
}
```

---

## Error Responses

All errors follow:
```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "timestamp": "2026-04-03T12:00:00Z"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Bad request / validation error |
| 401 | Missing or invalid `X-API-Key` |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 502 | n8n or upstream service unreachable |
| 500 | Internal server error |
