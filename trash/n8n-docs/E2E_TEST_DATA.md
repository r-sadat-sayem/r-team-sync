# TeamSync E2E Test Data

Use these scenarios as copy/paste inputs for full-flow testing across chat, PRD generation, email delivery, and Jira approval.

## Scenario 1: Primary Happy Path

### Initial prompt

```text
I want to build a mobile expense tracking app for small business owners. They need to photograph receipts, auto-categorize expenses, and export reports to CSV. Target: iOS and Android, launch in Q3 2025.
```

### Typical follow-up answers

```text
Success metric: reduce manual expense entry time by 70%.
Target users: freelancers and teams of up to 10 people.
Key concern: offline mode because users travel frequently.
```

### Generation confirmation

```text
Yes, go ahead.
```

### Email form data

```text
Name: QA Tester
Email: qa.teamsync.demo@example.com
```

### Jira approval data

```text
Decision: APPROVE
Notes: Approved for demo validation.
```

### Expected observations

- Sam asks 1 to 3 clarifying questions.
- A PRD is generated with a visible quality score, usually in the B to A range.
- The PRD includes FR items and TC test cases.
- Email is sent with a `.md` attachment.
- Jira creates one Epic, one Task, and one Subtask.

## Scenario 2: Fast Smoke Test

### Initial prompt

```text
Build a web app for HR teams to manage employee onboarding checklists, assign tasks, upload policy documents, and track completion status.
```

### Follow-up answers

```text
Target users: HR managers and new employees.
Timeline: internal beta in 6 weeks.
Success metric: reduce onboarding setup time by 50%.
```

### Confirmation

```text
Generate the PRD now.
```

### Email form data

```text
Name: Smoke Test
Email: smoke.teamsync.demo@example.com
```

### Jira approval data

```text
Decision: APPROVE
Notes: Smoke test run.
```

### Expected observations

- End-to-end flow completes without manual troubleshooting.
- PRD title should reflect onboarding or HR workflow language.
- Jira ticket summaries should map to the generated PRD content.

## Scenario 3: Weak Input Quality Check

Use this to confirm the validator reacts to poor input.

### Initial prompt

```text
I need an app for business stuff. Make it good and easy to use.
```

### Follow-up answers

```text
Users: everyone.
Timeline: soon.
Success metric: better productivity.
```

### Confirmation

```text
Yes, generate it.
```

### Expected observations

- Sam should ask for clarification before generating.
- The resulting PRD quality score should be lower than the main happy-path scenario.
- If the PRD still looks too generic, review prompt handling in n8n.

## Scenario 4: Email Validation Failure

Run the happy path through PRD generation, then submit:

```text
Name: 
Email: not-an-email
```

### Expected observations

- The React email form blocks submission.
- If invalid data reaches n8n directly, `Process Email Input` should reject it.

## Scenario 5: Jira Rejection Path

Run the happy path through PRD generation, then submit:

```text
Decision: REJECT
Notes: PRD needs refinement before ticket creation.
```

### Expected observations

- Jira tickets should not be created in the real workflow.
- Use this to confirm approval gating is working.

## Recommended Run Order

1. Run Scenario 1 to verify the full demo path.
2. Run Scenario 2 as a quick regression check after changes.
3. Run Scenario 4 and Scenario 5 for failure-path coverage.
4. Run Scenario 3 when checking prompt quality and validator behavior.
