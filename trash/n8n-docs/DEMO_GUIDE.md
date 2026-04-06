# TeamSync AI — Demo Guide (v2.1)

Presentation script for the PRD Automation POC. End-to-end run time: **5–8 minutes**.

Canonical references:
- [System Overview](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/system-overview.md)
- [Current Flow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/current-flow-reference.md)
- [Demo Deployment](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/demo-deployment.md)

---

## Prerequisites Checklist

Complete this before the call starts.

- [ ] **Ollama running** — `ollama serve` and model loaded: `ollama pull gpt-oss:20b-cloud`
- [ ] **n8n running** — workflow `team_sync_dev_v2.1_with_JIRA.json` imported and **activated**
- [ ] **JIRA credentials** — valid Jira credential configured in n8n
- [ ] **Gmail credentials** — valid Gmail OAuth2 credential configured in n8n
- [ ] **Demo endpoint configured** — the public review page can reach the same-origin chat path or direct chat link
- [ ] **Browser tab open** — `demo.html` loaded and chat widget visible
- [ ] **JIRA project visible** — open "Team Sync Automation" (project 10033) in another tab
- [ ] **Test run done** — run the full flow solo once before the presentation

---

## Recommended Demo Scenario

Use this exact input to avoid edge cases. It produces a good PRD score (≥70/100).

> **Starter message to Sam:**
> ```
> I want to build a mobile expense tracking app for small business owners.
> They need to photograph receipts, auto-categorize expenses, and export
> reports to CSV. Target: iOS and Android, launch in Q3 2025.
> ```

Sam will ask 1–3 clarifying questions. Answer naturally:
- Success metric: "Reduce manual expense entry time by 70%"
- Target users: "Freelancers and teams of up to 10 people"
- Key concern: "Offline mode — users travel frequently"

When Sam says it has enough and shows the `GENERATE_PRD:` summary, reply:
> ```
> Yes, go ahead
> ```

---

## Phase-by-Phase Script

### Phase 1 — Chat (1–2 min)
**What's happening:** Sam (the AI Product Analyst persona) is gathering requirements conversationally. Each message goes through n8n → Ollama → back to chat.

**Talking points:**
- "This is the requirements gathering phase. Sam is programmed to ask targeted questions and stop when it has enough context — not ask 20 questions."
- "Everything runs locally on this machine via Ollama. In production, you'd swap to a cloud LLM for consistency."
- "Session memory persists — Sam remembers what you said earlier in the conversation."

---

### Phase 2 — PRD Generation (1–3 min)
**What's happening:** n8n triggers the generate-mode prompt. The LLM writes a structured markdown PRD in a single response. This is the longest step due to the LLM output size (~5,000 words).

**Talking points:**
- "The PRD follows a strict template: Classification, Overview, Goals, Functional Requirements, Non-Functional Requirements, Scope, Success Metrics, Test Cases (15+), and JIRA ticket templates."
- "After generation, a quality scoring node evaluates the output — checking for required sections, test case count, and total length. Scores below 60 would require a retry."
- Watch for the quality score message in chat, e.g. `PRD Quality: 82/100 (B)`

---

### Phase 3 — Email Delivery (1 min)
**What's happening:** The PRD is base64-encoded and attached to a Gmail draft. A Wait node suspends the workflow and presents a form URL in chat.

**Talking points:**
- "The workflow pauses here — it's waiting for a recipient. This is n8n's HITL pattern: execution suspends, the form URL is live, and the workflow resumes only when submitted."
- Click the form URL from chat. Enter your name and email. Submit.
- "Within seconds the email lands with the `.md` file attached."

---

### Phase 4 — JIRA Approval (30 sec)
**What's happening:** Simultaneously with email, a second Wait node fires — an approval form for JIRA ticket creation.

**Talking points:**
- "This is the human-in-the-loop moment for JIRA. The system doesn't just auto-create tickets — a human reviews and approves first. This is intentional: the PRD might need edits before the team sees JIRA tickets."
- Open the JIRA approval form URL (shown in the n8n execution log or workflow output).
- Type `APPROVE` in the Decision field. Submit.

---

### Phase 5 — JIRA Tickets Created (30 sec)
**What's happening:** n8n resumes, parses the PRD for the first functional requirement and first test case, then creates: Epic → Task (child of Epic) → Subtask (child of Task, assigned to Basic Coding Agent).

**Switch to JIRA tab.**

**Talking points:**
- "The Epic title comes from the `**Project Name**` field in the PRD — not a generic label."
- "The Task maps to FR1 (first Functional Requirement). A full implementation would loop over all FRs."
- "The Subtask is TC001 — the first test case from the PRD. It's pre-assigned to the dev automation agent."
- Show the JIRA hierarchy: Epic > Task > Subtask.

---

## Expected Quality Scores

| Input quality | Expected score | Grade |
|---|---|---|
| Full scenario above | 75–90 | B–A |
| Minimal input | 50–65 | D–C |
| Very brief | < 50 | F (re-prompt) |

---

## Timing Guide

| Phase | Expected time |
|---|---|
| Chat with Sam (3–5 messages) | 1–2 min |
| PRD generation | 1–3 min |
| Email form + delivery | < 1 min |
| JIRA approval + creation | < 1 min |
| **Total** | **5–8 min** |

---

## Known Limitations (Be Upfront)

Tell the audience these — it builds trust and shows you know the system.

1. **Local LLM**: Ollama runs on this machine. Speed depends on available RAM/GPU. Production would use OpenAI or Gemini for consistency and speed.

2. **Single-ticket JIRA loop**: The current implementation creates 1 Epic + 1 Task + 1 Subtask per run (the first FR and TC only). A production version would loop over all requirements.

3. **JIRA field mapping**: The `parentIssueKey` field links tasks to epics in next-gen (team-managed) projects. Classic JIRA boards may need `customfield_10014` (Epic Link) instead.

4. **No retry loop**: If the PRD quality score is below threshold, the workflow still continues. A production version would re-prompt the LLM for a higher-quality output.

---

## If the Live Demo Fails

### LLM is slow / timed out
- Say: "Generation can take longer on local hardware — this would be faster with a cloud model."
- Show a pre-generated PRD file if available.

### JIRA authentication error
- Check that the JIRA credential in n8n is still valid (re-authenticate if needed).
- Fallback: show the JIRA ticket templates section at the bottom of the PRD markdown.

### Email not delivered
- Check Gmail credential OAuth2 token hasn't expired.
- Show the `.md` binary in n8n's execution data as proof of generation.

### Chat widget doesn't load in demo.html
- Open the direct chat link from the page instead of the iframe.
- Confirm the demo container is proxying `/webhook/*` to the active n8n instance.

---

## Post-Demo Talking Points

- "The entire backend is a single n8n workflow — 20 nodes, no custom server."
- "Swapping the LLM is one credential change. The prompt engineering lives in a Code node."
- "The JIRA branch currently creates one of each. The architecture for looping all FRs is straightforward — this is a POC scope decision, not a technical blocker."
- "Next steps: cloud LLM, full FR loop, Slack/Teams notification, multi-project JIRA support."
