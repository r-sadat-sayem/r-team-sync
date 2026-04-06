# 🤖 Automation Development Skills
### Complete Knowledge Base: n8n · Zapier · Make.com
> Version 2.1 · April 2026 · Covers: Design → Build → Debug → Deploy → Operate

---

## TABLE OF CONTENTS

1. [Foundations & Mental Models](#1-foundations--mental-models)
2. [Core Technical Prerequisites](#2-core-technical-prerequisites)
3. [n8n Mastery](#3-n8n-mastery)
4. [Zapier Mastery](#4-zapier-mastery)
5. [Make.com Mastery](#5-makecom-mastery)
6. [Cross-Platform Patterns](#6-cross-platform-patterns)
7. [AI & LLM Integration](#7-ai--llm-integration)
8. [Debugging & Quality Assurance](#8-debugging--quality-assurance)
9. [Security & Compliance](#9-security--compliance)
10. [Local Development Pipeline](#10-local-development-pipeline)
11. [Production Deployment Pipeline](#11-production-deployment-pipeline)
12. [Monitoring & Operations](#12-monitoring--operations)
13. [Workflow as a Product](#13-workflow-as-a-product)
14. [Reference Cheatsheets](#14-reference-cheatsheets)

---

## 1. Foundations & Mental Models

### 1.1 What Automation Engineers Actually Do
Automation engineers bridge business processes and technical systems. The job is not "connecting App A to App B" — it is **architecting reliable, observable, scalable data pipelines** that survive real-world chaos (API failures, schema changes, rate limits, bad input data).

### 1.2 The Automation Hierarchy of Needs
```
Level 5 — Agentic / AI-driven (self-correcting, goal-seeking)
Level 4 — Intelligent (LLM-augmented decisions, RAG, memory)
Level 3 — Complex (multi-branch, loops, sub-workflows, HITL)
Level 2 — Robust (error handling, retries, logging, alerts)
Level 1 — Functional (it works in happy path)          ← most people stop here
Level 0 — Manual process                                ← the baseline you replace
```
Always build at **Level 2 minimum** before shipping any workflow.

### 1.3 Workflow Lifecycle
```
Discovery → Design → Build → Test → Review → Deploy → Monitor → Iterate
```

### 1.4 Platform Selection Matrix

| Criteria              | n8n           | Zapier          | Make.com        |
|-----------------------|---------------|-----------------|-----------------|
| Self-host / data sovereignty | ✅ Best | ❌ No         | ⚠️ Limited     |
| Visual complexity     | High          | Low–Medium      | High            |
| Code customisation    | JS + Python   | JS (Code step)  | JS functions    |
| Cost at scale         | Cheapest      | Most expensive  | Mid-range       |
| AI / agent support    | ✅ Native     | ✅ Zapier AI    | ✅ Make AI      |
| Learning curve        | Medium–High   | Low             | Medium          |
| Best for              | Devs/Teams    | Non-technical   | Power users     |
| CI/CD / Git           | ✅ JSON export| ⚠️ Manual      | ⚠️ Manual      |
| Integrations          | 500+          | 8,700+          | 2,000+          |

---

## 2. Core Technical Prerequisites

### 2.1 Must-Know Languages & Formats
- **JavaScript (ES2020+)** — primary scripting language across all three platforms
  - Array methods: `map`, `filter`, `reduce`, `find`, `flatMap`
  - Destructuring, spread/rest, optional chaining (`?.`), nullish coalescing (`??`)
  - Async/await, Promise handling, try/catch/finally
  - `JSON.parse` / `JSON.stringify`, date manipulation
- **Python** — required for n8n Python Code nodes and scripting helpers
- **JSON / JSONPath** — data mapping, response parsing, schema validation
- **Regex** — text extraction, validation patterns, data cleaning
- **Markdown** — documentation, PRD generation, template formatting

### 2.2 API Fundamentals
- HTTP verbs: GET, POST, PUT, PATCH, DELETE and when to use each
- Status codes: 2xx (success), 3xx (redirect), 4xx (client error), 5xx (server error)
- Auth methods: API Key (header/query), Bearer Token, OAuth 2.0 (PKCE, client credentials, authorization code), Basic Auth, HMAC signatures
- Request anatomy: headers, query params, body (JSON, form-data, multipart)
- Pagination strategies: cursor, offset/limit, page-based, link headers
- Rate limiting: `Retry-After` headers, exponential backoff, token buckets
- Webhooks: push vs. poll, payload verification (HMAC), idempotency keys

### 2.3 Data Concepts
- Normalisation, deduplication, enrichment, transformation
- Binary data handling (base64 encode/decode, MIME types, file buffers)
- Schema validation (Zod, JSON Schema, ajv)
- Incremental processing (track last-processed cursor, avoid full re-runs)
- Idempotency: safe to re-run without side effects

### 2.4 DevOps Baseline
- **Git**: branches, commits, PRs, `.gitignore` for credentials
- **Docker**: images, containers, volumes, `docker-compose.yml`
- **Environment variables**: `.env` files, secrets managers (Vault, AWS SSM, Docker Secrets)
- **Reverse proxy basics**: Nginx/Caddy for SSL termination and routing
- **Linux CLI**: file permissions, cron, systemd, logs (`journalctl`, `tail -f`)

---

## 3. n8n Mastery

### 3.1 Architecture & Key Concepts
- **Node types**: Trigger, Action, Logic (IF, Switch, Merge, Loop), Transform (Code, Set, Function), AI
- **Data model**: every node receives and outputs an **array of items** (`[{json:{}, binary:{}}]`)
- **Expressions**: `{{ $json.field }}`, `{{ $node["NodeName"].json.field }}`, `{{ $items("NodeName", 0, 0) }}`
- **Execution modes**: manual (test), production (active), sub-workflow
- **Sessions**: `sessionId` for memory-backed conversations (Window Buffer Memory)

### 3.2 Node Reference — Critical Nodes

#### Trigger Nodes
| Node | Use Case |
|------|----------|
| Chat Trigger | Embeddable chat widget with `initialMessages`, file upload, session |
| Webhook | Receives HTTP requests; use `webhookId` for stable URLs |
| Schedule | Cron-based; prefer `0 */6 * * *` style expressions |
| Email Trigger (IMAP) | Poll inbox for new messages |

#### Logic & Flow
| Node | Use Case |
|------|----------|
| IF | Binary branching on conditions |
| Switch | Multi-route (up to N outputs) with `fallbackOutput` |
| Merge | Combine streams: Wait, Append, Multiplex, Pass-Through |
| Split in Batches | Loop over array items `batchSize: 1` for per-item processing |
| Wait | Pause for webhook resume, form submission, or time delay |
| NoOp | Route placeholder; use for readable "Continue" / "Done" labels |

#### Data Transformation
| Node | Use Case |
|------|----------|
| Code (JS/Python) | Custom logic, multi-item processing, binary data |
| Set | Add/overwrite fields, clean up payload |
| Edit Fields | Map fields visually |
| HTML Extract | Scrape DOM elements |
| XML | Parse/serialise XML |
| Crypto | Hash, HMAC signature verification |

#### AI / LangChain Nodes
| Node | Use Case |
|------|----------|
| AI Agent | Multi-turn agent with tools, memory, fallback LLM |
| lmChatOpenAI / lmChatOllama | LLM connectors (primary + fallback pattern) |
| memoryBufferWindow | Sliding window conversation memory |
| Tool: Code / Webhook / HTTP | Give agents callable tools |
| Vector Store (Pinecone, Qdrant, Supabase) | RAG retrieval |

### 3.3 Expression Language Patterns
```javascript
// Access current item
{{ $json.email }}

// Access item from another node
{{ $node["Node Name"].json.field }}

// Conditional expression
{{ $json.status === 'active' ? 'yes' : 'no' }}

// Default value
{{ $json.name ?? 'Unknown' }}

// Current ISO date
{{ $now.toISO() }}

// Format date
{{ $now.format('yyyy-MM-dd') }}

// Loop index (inside SplitInBatches)
{{ $runIndex }}

// Access binary data filename
{{ $binary.data.fileName }}

// Webhook resume URL
{{ $execution.resumeFormUrl }}
```

### 3.4 Code Node Best Practices
```javascript
// ✅ Standard Code Node Template
try {
  const input = $input.first().json;
  
  // Validate required fields
  if (!input.email) throw new Error('Missing required field: email');
  
  // Process
  const result = {
    ...input,
    processedAt: new Date().toISOString(),
    normalized: input.email.toLowerCase().trim()
  };
  
  console.log('✅ [NodeName] processed:', result.email);
  return [{ json: result }];
  
} catch (err) {
  console.error('❌ [NodeName]:', err.message);
  throw new Error('[NodeName] ' + err.message); // Preserves node name in error
}
```

```javascript
// ✅ Processing all items in a Code Node
try {
  const items = $input.all();
  return items.map(item => {
    const { name, email } = item.json;
    return { json: { name: name.trim(), email: email.toLowerCase() } };
  });
} catch (err) {
  throw new Error('[TransformNode] ' + err.message);
}
```

### 3.5 Error Handling Architecture
```
Trigger → ... → Node (might fail) → Error branch (IF on error field)
                                  ↓
                           Error Handler Node
                                  ↓
                     Notify (Slack/Email) + Log + Retry or Dead Letter
```
- Enable **"On Error: Continue"** on non-critical nodes to prevent full workflow failure
- Use **Try/Catch in Code nodes** — never let `.json` access fail silently
- Set workflow-level **error workflow** in Settings → Error Trigger
- Implement **dead letter queues** using a dedicated "Failed Executions" Airtable/sheet

### 3.6 Sub-Workflow Pattern
```
Main Workflow
  └── Execute Sub-Workflow: "process_single_record"
        (pass: { record, sessionId, config })
        (return: { success, result, error })
```
Benefits: reusability, testability, separation of concerns, easier debugging.

### 3.7 Human-in-the-Loop (HITL) Pattern
```
Generate output → Convert to Binary → Wait Node (form resume)
                                            ↓
                                   User submits form
                                            ↓
                              Merge (binary + form data) → Continue
```
- Always set a `limitWaitTime: 24h` on Wait nodes to prevent zombie executions
- Use `$execution.resumeFormUrl` to embed the form URL in notifications

### 3.8 JIRA / Project Management Integration Pattern
```
PRD/Data → Extract Content Node (regex parse) → Create Epic → Loop Over Tasks
                                                                   ↓
                                                          Create Parent Task
                                                                   ↓
                                                         Prepare Subtask Items
                                                                   ↓
                                                         Loop Over Subtasks → Create Subtask
```

---

## 4. Zapier Mastery

### 4.1 Core Architecture
- **Zap** = Trigger + one or more Actions (linear or multi-path)
- **Paths** = conditional branching (like IF/Switch in n8n)
- **Formatter** = built-in data transformation (dates, text, numbers, utilities)
- **Filter** = conditional execution gate (stops Zap if condition fails)
- **Delay** = time-based pausing before next action
- **Looping by Zapier** = process array items one-by-one

### 4.2 Zapier Developer Skills Stack
- **Zap Builder** — drag-and-drop, field mapping, test & review
- **Code by Zapier** — JavaScript or Python for custom transformations
- **Webhooks by Zapier** — send/catch arbitrary HTTP requests
- **API Requests** — call any REST API not in the App Directory
- **Zapier Interfaces** — build forms, dashboards, chatbot UIs as workflow front-ends
- **Zapier Tables** — built-in no-code database for workflow state
- **Zapier Canvas** — visual workflow diagramming and documentation
- **Zapier Agents (AI)** — autonomous agents with natural language task handling
- **Zapier Chatbots** — deployable AI chatbots that trigger workflows
- **Zapier Developer Platform** — build custom app integrations (CLI-based)
- **Zapier MCP** — connect AI agents (Claude, GPT) to 8,000+ apps

### 4.3 Code by Zapier Template
```javascript
// Input fields: inputData.email, inputData.name
const email = inputData.email?.toLowerCase()?.trim();
const name = inputData.name?.trim();

if (!email || !email.includes('@')) {
  throw new Error('Invalid email: ' + email);
}

// Zapier Code must return an object
output = { 
  normalizedEmail: email,
  normalizedName: name,
  processedAt: new Date().toISOString()
};
```

### 4.4 Environment Management in Zapier
Zapier has no native dev/staging/prod environments. Best practices:
- Use **folder organisation**: `[DEV]`, `[STAGING]`, `[PROD]` prefixes on Zap names
- Maintain **duplicate Zaps** for each environment; use different webhook URLs
- Use **Zapier Interfaces** as the user-facing layer (separate from automation logic)
- Store environment config in **Zapier Tables** (lookup table pattern)
- For org-level CI/CD, use the **Zapier Workflow API** (embed product use case)

### 4.5 Zapier AI Integration
```
AI by Zapier → Prompt with context → Parse JSON output → Continue Zap
                    ↓
       Supported models: GPT-4o, Claude 3.5, Gemini
       Use structured output prompts → JSON with defined keys
```

---

## 5. Make.com Mastery

### 5.1 Core Architecture
- **Scenario** = equivalent of Workflow/Zap
- **Module** = equivalent of Node/Step
- **Bundles** = Make's term for data items (like n8n items)
- **Router** = splits execution into parallel branches
- **Aggregator** = merges multiple bundles into one
- **Iterator** = processes array items one-by-one
- **Data Store** = built-in key-value database per scenario

### 5.2 Key Make.com Modules
| Module | Purpose |
|--------|---------|
| HTTP | Generic REST API calls, full control |
| Webhooks | Receive/send webhook events |
| Router | Branch on conditions (up to 10 routes) |
| Iterator | Loop over arrays |
| Array Aggregator | Collect loop results |
| JSON | Parse / Create JSON |
| Text Parser | Regex, HTML parsing |
| Data Store | Persistent key-value storage |
| Flow Control | Sleep, Break, Ignore |

### 5.3 Inline Functions Reference
```javascript
// String manipulation
{{lower(1.email)}}           // lowercase
{{trim(1.name)}}             // remove whitespace
{{substring(1.text; 0; 100)}} // first 100 chars
{{replace(1.url; "http"; "https")}} // replace string
{{split(1.tags; ",")}}       // string to array

// Date/Time
{{now}}                      // current datetime
{{formatDate(now; "YYYY-MM-DD")}}
{{addDays(now; 7)}}

// Math & Logic
{{if(1.score > 80; "pass"; "fail")}}
{{round(1.amount; 2)}}
{{sum(arrayOfNumbers)}}

// Arrays
{{length(1.items)}}
{{first(1.items)}}
{{map(1.items; "name")}}     // extract property from array
```

### 5.4 Make.com Error Handling
- **Error Handler routes**: Add after any module → choose: Ignore, Rollback, Commit, Resume, Break
- **Break with auto-retry**: configures automatic retry with exponential backoff
- **Incomplete Executions**: Make saves failed scenarios for manual re-run
- Best practice: use **Rollback** for transactional flows (write operations), **Ignore** for read-only enrichment

### 5.5 Make Bridge & Embedded Automation
- **Make Bridge (Beta)**: embed 2,000+ integrations directly into your SaaS product
- Users automate inside your platform; Make handles auth, API maintenance, security
- Use case: white-label automation marketplace within your product

---

## 6. Cross-Platform Patterns

### 6.1 Universal Workflow Architecture Pattern
```
[Trigger] → [Validate & Sanitize Input] → [Core Business Logic]
                                                    ↓
                                         [Error Handler] ←──────┐
                                                    ↓             │
                                         [Transform Output]       │
                                                    ↓             │
                                         [Write/Send Result]      │
                                                    ↓             │
                                         [Log & Notify] ──────────┘
```

### 6.2 Retry with Exponential Backoff (universal)
```javascript
async function retryWithBackoff(fn, maxRetries = 3) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt === maxRetries - 1) throw err;
      const delay = Math.pow(2, attempt) * 1000 + Math.random() * 500;
      await new Promise(r => setTimeout(r, delay));
    }
  }
}
```

### 6.3 Idempotency Pattern
```javascript
// Generate deterministic ID from input data
const idempotencyKey = require('crypto')
  .createHash('sha256')
  .update(JSON.stringify({ orderId, eventType, timestamp }))
  .digest('hex');

// Check if already processed (Airtable / Redis / Supabase lookup)
// If found → skip; If not → process → mark as processed
```

### 6.4 Pagination Handler Pattern
```javascript
let allResults = [];
let page = 1;
let hasMore = true;

while (hasMore) {
  const response = await fetch(`${API_URL}?page=${page}&limit=100`);
  const data = await response.json();
  allResults = allResults.concat(data.items);
  hasMore = data.hasNextPage;
  page++;
}
```

### 6.5 Webhook Security Verification
```javascript
// HMAC signature verification
const crypto = require('crypto');
const payload = JSON.stringify(requestBody);
const expectedSig = crypto
  .createHmac('sha256', process.env.WEBHOOK_SECRET)
  .update(payload)
  .digest('hex');

if (receivedSignature !== `sha256=${expectedSig}`) {
  throw new Error('Invalid webhook signature — rejecting request');
}
```

---

## 7. AI & LLM Integration

### 7.1 LLM Integration Architecture
```
User Input → [Context Builder] → [System Prompt + Memory] → [LLM Call]
                                                                   ↓
                                              [Parse & Validate LLM Output]
                                                                   ↓
                                               [Route on Action/Intent]
                                                   ↓           ↓
                                              [Tool Use]   [Return Response]
```

### 7.2 Prompt Engineering Fundamentals
**Zero-shot**: Direct instruction, no examples  
**Few-shot**: Provide 2-3 examples before the task  
**Chain-of-Thought**: Ask model to reason step-by-step  
**Structured Output**: Demand JSON with defined schema  
**Role Priming**: "You are an expert [X] who..."  
**Constraint Injection**: "Respond ONLY with a JSON object. No preamble."

### 7.3 System Prompt Architecture Template
```
[ROLE DEFINITION]
You are [Name], an expert [domain] AI. Your purpose is [mission].

[OPERATING RULES]
- CRITICAL: [most important constraint]
- [Rule 2]
- [Rule 3]
- Avoid: [anti-patterns]

[OUTPUT FORMAT]
When [condition], respond EXACTLY:
[FORMAT TEMPLATE WITH EXAMPLES]

[CONTEXT INJECTION]
{{ contextSummary }}
{{ currentDate }}
```

### 7.4 Structured JSON Output Enforcement
```
System Prompt:
"Respond ONLY with valid JSON. No markdown, no backticks, no explanation.
Schema: { "action": "continue|generate|done", "summary": "string", "data": {} }"

Parsing:
let raw = llmOutput.replace(/```json|```/g, '').trim();
const parsed = JSON.parse(raw); // wrap in try/catch
```

### 7.5 RAG (Retrieval-Augmented Generation) Pipeline
```
[User Query] → [Embed Query (OpenAI/local)] → [Vector Search (Pinecone/Qdrant/Supabase)]
                                                           ↓
                                              [Retrieve top-K chunks]
                                                           ↓
                                          [Inject into LLM context window]
                                                           ↓
                                                  [LLM Response]
```
Tools: Pinecone, Qdrant, Supabase pgvector, Weaviate, ChromaDB  
Embedding models: `text-embedding-3-small` (OpenAI), `nomic-embed-text` (local)

### 7.6 Agentic Workflow Pattern
```
[User Input / Trigger]
        ↓
[Planner: Break task into subtasks]
        ↓
[Executor Loop]
  → [Select Tool / Sub-workflow]
  → [Execute Tool]
  → [Evaluate Result vs Goal]
  → [Self-correct or continue]
        ↓
[Memory Update (buffer/vector)]
        ↓
[Final Response / Action]
```

### 7.7 AI Safety in Automation
- **Tool boundaries**: restrict agent to only declared tools, never open-ended shell exec
- **Human-in-the-loop checkpoints**: require approval before write/send operations
- **Prompt injection defence**: sanitise user input before injecting into prompts
- **Output validation**: always parse and validate LLM output before using in downstream nodes
- **Placeholder guard**: reject outputs containing `MyApp`, `[PROJECT NAME]`, `TBD` as final values
- **Rate limiting**: implement per-user/per-session limits on LLM calls

### 7.8 LLM Provider Integration Reference
| Provider | n8n Node | Auth | Notes |
|----------|----------|------|-------|
| OpenAI | lmChatOpenAI | API Key | GPT-4o recommended for agents |
| Anthropic Claude | lmChatAnthropic | API Key | Best for long-context |
| Ollama (local) | lmChatOllama | URL | mistral, llama3, qwen2.5 |
| Google Gemini | lmChatGoogleGemini | API Key | Gemini 2.0 Flash for speed |
| Groq | lmChatGroq | API Key | Fastest inference |

---

## 8. Debugging & Quality Assurance

### 8.1 Debugging Workflow (Systematic)
```
Step 1: Reproduce — run workflow with known test input
Step 2: Isolate — use "Execute Node" to test individual nodes
Step 3: Inspect — check input/output JSON at the failing node
Step 4: Hypothesis — form a specific theory about the failure
Step 5: Fix — apply minimal targeted change
Step 6: Verify — re-run with original + edge case inputs
Step 7: Document — add a sticky note explaining the fix
```

### 8.2 Common n8n Failure Patterns & Fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `Cannot read property X of undefined` | Missing field in upstream node | Add null check: `input?.field ?? 'default'` |
| Binary data lost after Wait/Merge | Merge node doesn't carry binary | Re-fetch from earlier node using `$items('Convert to Binary', 0, 0)` |
| Webhook returns 404 after redeploy | webhookId changed | Hardcode `webhookId` in node parameters |
| Agent loops infinitely | No termination signal detected | Add explicit `action:'done'` detection in Parse Response node |
| Rate limit (429) | Too many API calls | Add Wait node (1-2s) inside loops, implement backoff |
| CORS error in webhook | Missing headers | Add `Access-Control-Allow-Origin` in webhook response |
| `SyntaxError: Unexpected token` | LLM returned non-JSON | Strip ```json fences, use `.replace(/```json|```/g, '')` |
| Memory context lost | sessionId not passed through | Ensure `sessionId` propagates through all nodes |

### 8.3 Testing Strategy

#### Unit Testing (Node-level)
- Use **Execute Node** button to test individual nodes in isolation
- Use **Pin Data** to freeze upstream output for repeatable tests
- Validate output JSON shape and types before connecting to next node

#### Integration Testing (Workflow-level)
- Create a `test_payload.json` fixture for each trigger type
- Test: happy path → missing fields → unexpected data types → empty arrays → very large inputs
- Use **Manual Trigger + hardcoded test data** before activating

#### End-to-End Testing
- Use a dedicated **Staging webhook URL** (separate from production)
- Run real API calls against sandbox/test credentials
- Verify complete data flow from trigger to final output

### 8.4 Logging Best Practices
```javascript
// Use structured log prefix pattern for searchability
console.log('✅ [NodeName] Success:', { key: value });
console.warn('⚠️ [NodeName] Warning:', condition);
console.error('❌ [NodeName] Error:', err.message);

// Log critical state at branch points
console.log('🎯 [Router] Action detected:', action, '| Session:', sessionId);
console.log('📊 [Validator] Score:', score, '| Grade:', grade);
```

### 8.5 PRD / Output Quality Scoring Pattern
```javascript
// Quality gate before publishing any generated artifact
const qualityChecks = {
  hasRequiredSections: /Goals|Requirements|Scope/.test(output),
  minimumLength: output.length > 3000,
  hasTestCases: /TC\d{3}/.test(output),
  noPlaceholders: !/\[PROJECT NAME\]|\bTBD\b|MyApp/i.test(output)
};

const score = Object.values(qualityChecks).filter(Boolean).length;
if (score < 3) throw new Error(`Quality gate failed: ${JSON.stringify(qualityChecks)}`);
```

---

## 9. Security & Compliance

### 9.1 Credential Management
- **Never** hardcode API keys, passwords, or tokens in workflow JSON
- Use platform credential stores: n8n Credentials Manager, Zapier's secure credential storage
- For self-hosted n8n: use Docker Secrets or environment variables via `.env`
- Rotate credentials on a schedule; invalidate immediately on team member departure
- Use scoped API keys (read-only where sufficient, never admin keys for automation)

### 9.2 n8n Credential Security
```bash
# .env (never commit to git)
N8N_ENCRYPTION_KEY=your-32-char-random-key
DB_POSTGRESDB_PASSWORD=secure-password
WEBHOOK_SECRET=your-webhook-hmac-secret

# docker-compose secrets
secrets:
  n8n_encryption_key:
    file: ./secrets/encryption_key.txt
```

### 9.3 Data Security Checklist
- [ ] PII (names, emails, phone) is not logged in plaintext console output
- [ ] Webhook payloads are signature-verified before processing
- [ ] API responses are validated (don't trust external data shapes)
- [ ] Sensitive fields are masked/encrypted before storage
- [ ] HTTPS enforced for all external communication
- [ ] Firewall blocks direct access to n8n port (5678); only Nginx/Caddy exposed

### 9.4 RBAC (n8n Enterprise / Cloud)
- Assign roles: Owner, Admin, Member, Viewer
- Restrict workflow creation to specific roles in shared environments
- Separate environments: Development → Staging → Production instances
- Audit logs: enable `N8N_LOG_LEVEL=info` + stream to SIEM (Splunk, Datadog)

### 9.5 Compliance Patterns
- **GDPR**: implement data deletion workflows; log consent events; minimise data retention
- **HIPAA**: end-to-end encryption; audit logging; access controls; BAA with cloud providers
- **SOC 2**: change management via Git; incident response runbook; uptime monitoring

---

## 10. Local Development Pipeline

### 10.1 Local Environment Setup

#### n8n Local (Docker Compose)
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: n8n_dev
      POSTGRES_DB: n8n
    volumes:
      - postgres_dev:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U n8n']
      interval: 5s
      retries: 10

  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=n8n_dev
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=devpassword
      - EXECUTIONS_PROCESS=main
      - N8N_RUNNERS_ENABLED=true
    volumes:
      - n8n_dev:/home/node/.n8n
      - ./workflows:/workflows  # mount for JSON export/import
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_dev:
  n8n_dev:
```

```bash
# Start dev environment
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f n8n

# Stop
docker compose -f docker-compose.dev.yml down
```

### 10.2 Workflow Version Control with Git
```bash
# Project structure
automation-project/
├── workflows/
│   ├── team_sync_dev_v2.1.json       # exported n8n workflow
│   ├── lead_capture.json
│   └── prd_generator.json
├── docs/
│   ├── architecture.md
│   └── runbooks/
├── scripts/
│   ├── export_workflows.sh
│   └── import_workflows.sh
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .env.example                       # NEVER commit .env
├── .gitignore
└── README.md
```

```bash
# .gitignore
.env
.env.local
.env.prod
secrets/
n8n_data/
*.log
```

```bash
# export_workflows.sh — export all active workflows to JSON
#!/bin/bash
N8N_URL="http://localhost:5678"
AUTH="admin:devpassword"

mkdir -p ./workflows
WORKFLOWS=$(curl -s -u $AUTH "$N8N_URL/api/v1/workflows" | jq -r '.data[].id')

for WF_ID in $WORKFLOWS; do
  NAME=$(curl -s -u $AUTH "$N8N_URL/api/v1/workflows/$WF_ID" | jq -r '.name' | tr ' ' '_')
  curl -s -u $AUTH "$N8N_URL/api/v1/workflows/$WF_ID" > "./workflows/${NAME}_${WF_ID}.json"
  echo "✅ Exported: $NAME"
done
```

### 10.3 Local Testing Checklist
- [ ] Workflow imports cleanly from JSON with no node errors
- [ ] All credentials resolve (dev credentials configured locally)
- [ ] Manual trigger executes without errors on happy path data
- [ ] Each Code node tested with `Execute Node` in isolation
- [ ] Error path tested: what happens when upstream API returns 500?
- [ ] Webhook tested with `curl -X POST` or Postman/Insomnia
- [ ] Memory/session tested: does context persist across multiple chat turns?

---

## 11. Production Deployment Pipeline

### 11.1 Production Docker Compose
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      POSTGRES_DB: n8n
    volumes:
      - postgres_prod:/var/lib/postgresql/data
    secrets:
      - db_password
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U n8n']
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    # Required for n8n queue mode (scaling)

  n8n:
    image: n8nio/n8n:latest
    restart: always
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD_FILE=/run/secrets/db_password
      - N8N_ENCRYPTION_KEY_FILE=/run/secrets/encryption_key
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=redis
      - N8N_HOST=${DOMAIN}
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://${DOMAIN}/
      - N8N_LOG_LEVEL=info
      - N8N_METRICS=true
    volumes:
      - n8n_prod:/home/node/.n8n
    secrets:
      - db_password
      - encryption_key
    depends_on:
      postgres:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./certbot/conf:/etc/letsencrypt
    depends_on:
      - n8n

secrets:
  db_password:
    file: ./secrets/db_password.txt
  encryption_key:
    file: ./secrets/encryption_key.txt

volumes:
  postgres_prod:
  n8n_prod:
```

### 11.2 Nginx SSL Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://n8n:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";  # WebSocket support
        proxy_buffering off;
        proxy_read_timeout 3600;  # Long timeout for agent workflows
    }
}
```

### 11.3 CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/deploy.yml
name: Deploy n8n Workflows

on:
  push:
    branches: [main]
    paths:
      - 'workflows/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate workflow JSON
        run: |
          for f in workflows/*.json; do
            python3 -m json.tool "$f" > /dev/null && echo "✅ $f" || exit 1
          done

  deploy:
    needs: validate
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Import workflows to production n8n
        env:
          N8N_URL: ${{ secrets.PROD_N8N_URL }}
          N8N_API_KEY: ${{ secrets.PROD_N8N_API_KEY }}
        run: |
          for WORKFLOW_FILE in workflows/*.json; do
            WF_NAME=$(basename "$WORKFLOW_FILE" .json)
            WF_ID=$(curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
              "$N8N_URL/api/v1/workflows" | \
              jq -r --arg name "$WF_NAME" '.data[] | select(.name==$name) | .id')
            
            if [ -n "$WF_ID" ]; then
              # Update existing
              curl -s -X PATCH \
                -H "X-N8N-API-KEY: $N8N_API_KEY" \
                -H "Content-Type: application/json" \
                -d @"$WORKFLOW_FILE" \
                "$N8N_URL/api/v1/workflows/$WF_ID"
              echo "✅ Updated: $WF_NAME"
            else
              # Create new
              curl -s -X POST \
                -H "X-N8N-API-KEY: $N8N_API_KEY" \
                -H "Content-Type: application/json" \
                -d @"$WORKFLOW_FILE" \
                "$N8N_URL/api/v1/workflows"
              echo "➕ Created: $WF_NAME"
            fi
          done

      - name: Notify deployment
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "✅ Workflows deployed to production by ${{ github.actor }}"}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 11.4 Deployment Checklist
```
Pre-deployment:
[ ] All workflows exported as JSON and committed to Git
[ ] Code reviewed (logic, error handling, no hardcoded credentials)
[ ] Tested in staging environment with production-like data
[ ] Rollback plan documented (previous JSON committed, easy re-import)

Deployment:
[ ] Database backup created before deployment
[ ] Environment variables verified on target server
[ ] Docker images pulled and containers healthy
[ ] SSL certificate valid and not expiring within 30 days
[ ] DNS pointing to production server

Post-deployment:
[ ] Smoke test: trigger each workflow manually once
[ ] Monitor execution logs for first 30 minutes
[ ] Verify webhook URLs are reachable from external sources
[ ] Alert channels (Slack/email) confirmed working
[ ] Runbook updated with deployment notes
```

### 11.5 Sharing Workflows as Usable Artifacts

#### Option A: n8n Template Export
```bash
# Export as shareable template (strip credentials)
# 1. Open workflow → ... menu → Download
# 2. The JSON can be imported by anyone with n8n
# 3. Publish to n8n.io/workflows community
```

#### Option B: Dockerized Workflow Product
```yaml
# docker-compose.shareable.yml
# Ship your automation as a standalone Docker product
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    ports: ["5678:5678"]
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${ADMIN_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${ADMIN_PASS:-changeme}
    volumes:
      - ./workflows:/workflows-to-import
      - n8n_data:/home/node/.n8n
    entrypoint: >
      sh -c "
        n8n start &
        sleep 15 &&
        for f in /workflows-to-import/*.json; do
          n8n import:workflow --input=$$f
        done &&
        wait
      "
volumes:
  n8n_data:
```

#### Option C: Zapier/Make Public Templates
- Zapier: Settings → Share → Create template link
- Make.com: Scenario → Share template → Publish to template library

#### Option D: API-first Workflow Service
```
Your n8n instance → exposed as REST API via Webhook triggers
Consumers POST to: https://your-domain.com/webhook/workflow-name
Returns: JSON result

Use case: sell access to your automation as a micro-service
```

---

## 12. Monitoring & Operations

### 12.1 Observability Stack (Self-hosted n8n)
```
n8n Execution Logs → Log Aggregator (Loki / ELK)
                            ↓
                    Dashboard (Grafana / Kibana)
                            ↓
                    Alerting (PagerDuty / Slack)

Metrics to track:
- Execution success rate (target: >99%)
- Execution duration (P50, P95, P99)
- Error rate by workflow
- Queue depth (queue mode)
- Memory/CPU usage of n8n container
```

### 12.2 Alerting Rules
```javascript
// Alert conditions (implement via n8n Error Workflow or external monitoring)
const alerts = [
  { name: "High error rate", condition: "errors > 5% in 10 min" },
  { name: "Execution timeout", condition: "duration > 5 min for workflow X" },
  { name: "Webhook silent", condition: "no executions in 1 hour for trigger Y" },
  { name: "Queue backup", condition: "queue depth > 100 items" },
  { name: "Disk space", condition: "disk usage > 80%" }
];
```

### 12.3 Maintenance Schedule
| Frequency | Task |
|-----------|------|
| Daily | Review execution error logs; check disk space |
| Weekly | Verify backups are restorable; review slow executions |
| Monthly | Rotate API keys; patch Docker images; clean old execution logs |
| Quarterly | Disaster recovery drill; review RBAC permissions; audit credential access |

### 12.4 Backup Strategy
```bash
#!/bin/bash
# backup.sh — run via cron daily at 02:00
BACKUP_DIR=/opt/n8n/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Backup PostgreSQL
docker exec n8n-postgres-1 pg_dump -U n8n n8n | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup n8n data directory
tar czf $BACKUP_DIR/n8n_data_$DATE.tar.gz /opt/n8n/data

# Export all workflows as JSON
for WF_ID in $(curl -s -H "X-N8N-API-KEY: $API_KEY" http://localhost:5678/api/v1/workflows | jq -r '.data[].id'); do
  curl -s -H "X-N8N-API-KEY: $API_KEY" "http://localhost:5678/api/v1/workflows/$WF_ID" > $BACKUP_DIR/wf_${WF_ID}_$DATE.json
done

# Retain only last 30 days
find $BACKUP_DIR -mtime +30 -delete

echo "✅ Backup complete: $DATE"
```

---

## 13. Workflow as a Product

### 13.1 Productisation Checklist
- [ ] Workflow handles ALL edge cases (empty input, null values, API downtime)
- [ ] Clear user-facing error messages (not raw JS stack traces)
- [ ] HITL (Human-in-the-loop) gates for sensitive operations
- [ ] Configurable via environment variables (no hardcoded business logic)
- [ ] Documented: README, architecture diagram, setup guide
- [ ] Versioned: semantic versioning (`v1.2.0`) on exported JSON filenames
- [ ] Tested: happy path + failure scenarios documented and reproducible

### 13.2 Documentation Template
```markdown
# Workflow: [Name] v[X.Y.Z]

## Purpose
One paragraph describing what this workflow does and why.

## Trigger
- Type: Webhook / Schedule / Chat / Manual
- Endpoint: https://your-domain.com/webhook/[id]
- Payload schema: { field: type, ... }

## Architecture
[Include Mermaid diagram or screenshot]

## Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| SMTP_HOST | Email server | - |

## Error Handling
- Node X may fail if: [condition] → handled by: [approach]
- Dead letter: failed items stored in Airtable [link]

## Maintenance
Last updated: YYYY-MM-DD | Owner: [name]
```

### 13.3 Monetisation Models for Automation Products
- **SaaS automation**: expose n8n workflows as API endpoints, charge per-call
- **Template marketplace**: sell on n8n.io community, Gumroad, or your own store
- **Managed service**: run automation on behalf of clients (agency model)
- **Embedded automation** (Make Bridge / Zapier OEM): integrate into client's SaaS product
- **AI agents as service**: build specialised agents, deploy as chat interfaces

---

## 14. Reference Cheatsheets

### 14.1 n8n Key Environment Variables
```bash
# Core
N8N_ENCRYPTION_KEY=         # 32-char random string, CRITICAL
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=

# Database
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=postgres
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=n8n
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=

# Networking
N8N_HOST=your-domain.com
N8N_PORT=5678
N8N_PROTOCOL=https
WEBHOOK_URL=https://your-domain.com/

# Scaling
EXECUTIONS_MODE=queue        # 'regular' (default) or 'queue'
QUEUE_BULL_REDIS_HOST=redis
N8N_CONCURRENCY_PRODUCTION_LIMIT=10

# Logging & Monitoring
N8N_LOG_LEVEL=info           # debug | info | warn | error
N8N_METRICS=true
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=336  # hours (14 days)
```

### 14.2 Common API Testing Commands
```bash
# Test webhook trigger
curl -X POST https://your-domain.com/webhook/your-webhook-id \
  -H "Content-Type: application/json" \
  -d '{"test": true, "email": "test@example.com"}'

# Test n8n API (list workflows)
curl -H "X-N8N-API-KEY: your-api-key" \
  https://your-domain.com/api/v1/workflows

# Trigger a workflow via API
curl -X POST "https://your-domain.com/api/v1/workflows/[ID]/run" \
  -H "X-N8N-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"startNodes": ["Node Name"], "runData": {}}'
```

### 14.3 JavaScript Utility Snippets
```javascript
// Safe JSON parse
const safeJson = (str) => {
  try { return JSON.parse(str); } catch { return null; }
};

// Strip LLM markdown fences
const cleanLLMOutput = (raw) =>
  raw.replace(/```json\n?|```\n?/g, '').trim();

// Generate UUID (n8n Code Node)
const id = require('crypto').randomUUID();

// Base64 encode/decode
const b64 = Buffer.from(text, 'utf8').toString('base64');
const decoded = Buffer.from(b64, 'base64').toString('utf8');

// Slugify filename
const slug = (str) => str.toLowerCase()
  .replace(/[^a-z0-9\s\-_]/g, '')
  .replace(/\s+/g, '_')
  .substring(0, 50);

// Truncate text to token-safe length
const truncate = (text, maxChars = 3000) =>
  text.length > maxChars ? text.substring(0, maxChars) + '...' : text;
```

### 14.4 Prompt Engineering Quick Patterns
```
[STRUCTURED OUTPUT]
"Respond ONLY with valid JSON, no markdown, no explanation.
Schema: { action: string, data: object, confidence: number }"

[CHAIN OF THOUGHT]
"Think step by step before answering. Show your reasoning."

[FEW-SHOT]
"Here are examples:
Input: X → Output: Y
Input: A → Output: B
Now process: [user input]"

[CONSTRAINT INJECTION]
"Rules: (1) Never mention competitors. (2) Max 3 bullet points.
(3) If unsure, say 'I need more information about [X]'."

[ROLE + CONTEXT]
"You are [Name], an expert [role]. Today is {{ $now.toISO() }}.
Context: {{ contextSummary }}
Task: {{ userMessage }}"
```

### 14.5 Make.com vs n8n vs Zapier Quick Decision
```
If the user is non-technical and needs to set up fast → Zapier
If the user needs visual power + cost efficiency + moderate tech → Make.com
If the user is a developer, needs self-hosting, AI agents, or Git CI/CD → n8n
If the user needs to embed automation inside their own product → Make Bridge or Zapier OEM
If the user needs local + open source + full data ownership → n8n self-hosted
```

---

*Document maintained by: Sam (n8n Workflow Architect)*  
*Last updated: April 2026 | Based on n8n v1.x, Zapier 2025, Make.com 2025*  
*Sources: n8n docs, Zapier dev guide, Make.com docs, production deployment guides*
