# TeamSync AI v2.0 — User Guide & E2E Test Script

## Overview

TeamSync AI lets you describe a product idea in plain language, generates a scored PRD, emails it to a recipient, and creates JIRA tickets — all from a single conversation.

**Full flow:** Sign up → Chat with Sam → PRD artifact → Confirm email → Email sent → Confirm JIRA → Tickets created → Continue chatting

---

## Step 0 — Prerequisites (one-time setup)

### Minimum required env vars

Copy `backend/.env.example` to `backend/.env` and fill in at minimum:

```env
# AI (required — nothing works without this)
RAKUTEN_AI_GATEWAY_KEY=raik-your-key-here
RAKUTEN_ANTHROPIC_BASE_URL=https://api.ai.public.rakuten-it.com/anthropic/
RAKUTEN_ANTHROPIC_MODEL=claude-3-7-sonnet-20250219

# Database (required)
DATABASE_URL=postgresql+asyncpg://teamsync:teamsync@localhost:5432/teamsync

# Email fallback (simplest option — no OAuth setup needed)
GMAIL_SENDER=your-gmail@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # 16-char Google App Password

# JIRA fallback (simplest option — no OAuth setup needed)
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=TSA
```

> **Gmail App Password:** Google Account → Security → 2-Step Verification → App Passwords → generate one for "Mail".
> **JIRA API Token:** https://id.atlassian.com/manage-profile/security/api-tokens

### Start the stack

```bash
cd team-syncv2.0-fullstack

# Option A — Docker (recommended)
docker compose up --build -d

# Option B — manual
# Terminal 1
cd backend && pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:5173      |
| Backend  | http://localhost:8000      |
| API docs | http://localhost:8000/docs |

---

## Step 1 — Create an account

1. Open http://localhost:5173
2. You are redirected to `/login` → click **"Create one"**
3. Fill in:
   - **Display Name:** `Test User`
   - **Email:** `testuser@example.com`
   - **Password:** `testpass123`
4. Click **Create account** → you land on the Chat page

---

## Step 2 — Start a conversation with Sam

Sam gathers requirements through natural dialogue. The fastest path to PRD generation is to give him all the information in one message.

### Minimum happy-path input (copy-paste this)

Paste the following as your **first message**:

```
I want to build a mobile expense tracking app called "SpendWise". 
It's a new product for iOS and Android. The key features are: 
receipt scanning with OCR, automatic expense categorization, 
monthly budget limits with alerts, and a simple dashboard showing 
spending by category. Target users are freelancers and small 
business owners who need to track work expenses for tax reporting. 
Timeline is 3 months. Success metric: users can submit an expense 
report in under 60 seconds.
```

**What Sam does:** He may ask 1–2 clarifying questions (e.g., "Does it need multi-currency support?"). Answer briefly:

```
Single currency for now. No team features needed — solo users only.
```

Sam will then emit the `GENERATE_PRD:` signal internally and switch to generation mode.

### Alternatively — trigger PRD generation immediately

If Sam asks questions and you want to skip to generation, answer all questions in one message and end with:

```
That covers everything. Please generate the PRD now.
```

---

## Step 3 — PRD generation (automatic)

Once Sam has enough context, the following happens automatically:

1. **Status bar shows:** `"Generating PRD document…"` with a spinner (no giant text wall)
2. After ~15–30 seconds: a **PRD artifact card** appears in the chat showing:
   - Project title + grade badge (e.g., `B · 84/100`)
   - Section count + test case count
   - Filename (e.g., `spendwise_2026-04-06.md`)

**Actions available on the card:**
- **▶ Preview** — expands first 600 chars inline
- **↓ Download .md** — saves the full PRD to your machine
- **Open in Viewer →** — navigates to the full formatted PRD viewer

---

## Step 4 — Email confirmation

Immediately after the artifact card, an email confirmation panel appears:

```
┌──────────────────────────────────────────────────────┐
│  PRD ready!  Would you like to email it?   [B · 84]  │
│  [ Send Email → ]    [ ↩ Skip ]                      │
└──────────────────────────────────────────────────────┘
```

### Happy path — send the email

1. Click **Send Email →** — the form fields expand
2. *(Optional)* Click **Connect Gmail** to send from your own Gmail account via OAuth
   - Or leave it — the backend uses the SMTP app password from `.env` as fallback
3. Fill in:
   - **Recipient name:** `Jane Doe`
   - **Recipient email:** `jane@example.com` *(use a real inbox you can check)*
4. Click **Send PRD**

**Expected result:** A status flash "Sending PRD to jane@example.com…" then the JIRA panel appears.

### Skip email (faster test)

Click **↩ Skip** → goes straight to Step 5.

---

## Step 5 — JIRA ticket creation

After email, the JIRA panel appears:

```
┌──────────────────────────────────────────────────────┐
│  Create JIRA tickets                                 │
│  [ Connect JIRA ]  (if Atlassian OAuth not set up)   │
│  Assignee email  (optional)                          │
│  Notes           (optional)                          │
│  [ Approve & Create ]    [ ↩ Skip ]                  │
└──────────────────────────────────────────────────────┘
```

### Happy path — create tickets

1. *(Optional)* Click **Connect JIRA** to use your own Atlassian identity via OAuth popup
   - Or leave it — the backend uses the API token from `.env` as fallback
2. Fill in:
   - **Assignee email:** `team@yourorg.com` *(or leave blank)*
   - **Notes:** `Sprint 1 — prioritize receipt scanning`
3. Click **Approve & Create**

**Expected result:**
- A JIRA result card appears in chat with links:
  ```
  ● Epic: TSA-1  (link to JIRA)
  ● Story: TSA-2
  ● Story: TSA-3
  ...
  ```

### Skip JIRA (faster test)

Click **↩ Skip** → workflow ends.

---

## Step 6 — Continue the conversation

After the workflow completes, a hint appears above the input:

> *PRD complete — ask a follow-up question or request refinements*

The input is re-enabled. Sam still has full context. Try:

```
Can you add a requirement for offline mode support?
```

Sam will respond and you can request a PRD regeneration or keep refining.

---

## Step 7 — History & session resume

1. Click **History** in the sidebar
2. Your PRD appears with grade, test-case count, and date
3. Click the **chat icon** (↩) to resume that session in the chat page
4. Send a new message — it continues from where the session left off on the backend

---

## Slash commands reference

After a PRD has been generated you can type any of the following commands directly in the chat input. Commands work as exact slash syntax **or** as natural language variants.

### Document generation commands

| Command | Natural language variants | What it does |
|---------|--------------------------|--------------|
| `/jira` | `create jira tickets`, `generate jira` | Regenerates the JIRA Epic + Story templates from the current PRD and streams the result into chat |
| `/testcases` | `generate test cases`, `create test cases` | Regenerates the full test-case suite (Happy Path + Edge Cases) from the current PRD |
| `/regenerate` | `start over`, `reset` | Discards the current PRD and restarts requirements gathering from scratch |

> **Note:** `/jira` and `/testcases` require a PRD to already exist in the session. If no PRD has been generated yet, Sam will continue gathering requirements normally.

### Informational commands (available any time)

| Command | What it does |
|---------|--------------|
| `/prd` | Prints a preview of the current PRD (first 800 chars) with grade and filename |
| `/summary` | Shows the requirements context summary Sam collected before generating the PRD |
| `/help` | Lists all available commands in chat |

### Typical post-PRD workflows

**Regenerate JIRA tickets after reviewing the PRD:**
```
/jira
```
Sam skips all questions and immediately streams fresh JIRA Epic + Story templates.

**Regenerate test cases with a note to Sam:**
```
/testcases
```
Streams a new test-case document (minimum 15 TCs, happy path + edge cases).

**Feed the PRD back to the agent and ask it to create JIRA content:**
```
/prd
```
Sam prints the PRD preview. You can then follow up:
```
Based on the PRD above, focus the JIRA stories on the authentication flows only.
/jira
```

**Start a new product from scratch without losing the session:**
```
/regenerate
```
State is cleared. Sam introduces himself and begins fresh requirements gathering.

**Check what requirements were gathered (before or after PRD):**
```
/summary
```

---

## Quick reference — Sam conversation guide

Sam needs 7 pieces of information before he generates. The fastest way is to provide them all upfront:

| Field           | What Sam needs                        | Example                                      |
|-----------------|---------------------------------------|----------------------------------------------|
| Project         | Exact name (no placeholders)          | `SpendWise`                                  |
| Type            | Feature / Enhancement / New Product   | `New Product`                                |
| Platform        | Web / iOS / Android / API / All       | `iOS and Android`                            |
| Key Features    | 3–5 bullet points                     | receipt scanning, budget alerts, dashboard   |
| Target Users    | Specific description                  | `freelancers tracking work expenses for tax` |
| Timeline        | Deadline or TBD                       | `3 months`                                   |
| Success Metric  | One measurable goal                   | `expense submission in under 60 seconds`     |

> Sam will ask up to 3 questions per turn. Give dense, specific answers to move through quickly.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Blank chat after login | Backend not running | `uvicorn src.main:app --reload --port 8000` |
| Sam never triggers PRD generation | Missing project name / too vague | Include all 7 fields from the table above |
| `prd_complete` fires but no artifact card | Frontend out of sync | Hard-refresh (`Cmd+Shift+R`), check browser console |
| Email step shows "Skip" only visible | Normal — confirm step by design | Click "Send Email →" to expand the form |
| Email fails with auth error | SMTP app password wrong | Verify 16-char app password in `.env` |
| JIRA create fails 404 | Wrong project key or base URL | Check `JIRA_PROJECT_KEY` and `JIRA_BASE_URL` in `.env` |
| Session resume doesn't load old messages | Expected — messages are per-device | History resume restores the server-side context; just type to continue |
| PRD grade is low (D/F) | Sparse requirements | Provide more detail; Sam needs all 7 fields with specifics |

---

## E2E checklist

Use this to verify the full flow works end-to-end:

- [ ] Can sign up with email + password
- [ ] Chat page loads after login
- [ ] Sam responds to first message
- [ ] Sam asks ≤3 follow-up questions
- [ ] PRD generation triggers automatically (no manual button)
- [ ] Streaming shows spinner, not raw markdown
- [ ] PRD artifact card appears with grade badge
- [ ] "Preview" toggle works inline
- [ ] "Download .md" saves a file
- [ ] Email confirm panel shows "PRD ready!" with grade
- [ ] "Send Email →" expands form fields
- [ ] Email is received at the recipient address
- [ ] JIRA panel appears after email
- [ ] "Approve & Create" creates tickets in JIRA board
- [ ] JIRA result card shows epic + story links
- [ ] Input re-enables with continuation hint
- [ ] Follow-up message is accepted and Sam responds
- [ ] History page shows the PRD
- [ ] Resume session from History → sending a message continues the right session
