# n8n Workflow Reference

## Primary Workflow

- File: `team_sync_dev_v2.1_with_JIRA.json`
- Role: active backend automation
- Pattern: single self-contained workflow with internal mode switching

## Logical Node Groups

### Session and memory

- Memory buffer uses a custom session key
- `sessionId` is the continuity key for the entire flow
- Context window is finite, so long conversations depend on the workflow’s summarized handoff rather than unbounded memory

Inputs:
- `sessionId`
- latest `chatInput`

Outputs:
- memory-aware prompt context for the current request

### Prompt construction

- Dynamic prompt assembly chooses the active persona and instructions based on `mode`
- Analyze mode drives targeted question asking
- Generate mode enforces the full PRD markdown shape

Key behavior:
- analyze mode is designed to emit `GENERATE_PRD:` once enough detail is captured
- generate mode expects a one-shot full PRD

### Agent execution

- The workflow calls the configured Ollama chat model
- Response text is fed into a parser stage rather than returned directly without inspection

Dependencies:
- active Ollama server
- installed model used by the workflow

### Agent response parsing

- Detects `GENERATE_PRD:`
- Extracts structured handoff context
- Distinguishes `continue`, `generate`, and `done`
- Guards against placeholder-style summaries

This stage is the control-plane decision point for the entire workflow.

### Action routing

- Implemented with a switch node
- Routes based on `action`

Branches:
- `continue`: conversational reply only
- `generate`: loop back into the workflow with generate mode
- `done`: validate PRD, prepare email path, and continue into Jira extraction

### PRD quality validation

- Runs regex-based section detection
- Counts test cases
- Factors output length into the final score
- Produces a numeric score and letter grade

Outputs:
- `qualityScore`
- `grade`
- `summary`
- missing section metadata

### Binary preparation and email handling

- Removes internal `<think>` sections from markdown
- Converts markdown to base64 binary
- Creates a filename
- Captures the wait-form resume URL

After the recipient form resumes:
- merges PRD binary with form input
- validates name and email
- sends the markdown via Gmail

### Jira extraction

- Extracts project name from `**Project Name**`
- Extracts Epic description from the Product Overview section
- Extracts up to a small set of functional requirements and test cases
- Falls back to generated defaults if extraction is sparse

Outputs:
- `epicTitle`
- `epicDescription`
- `tasks[]`
- `subtasks[]`

### Jira approval and creation

- Wait node pauses for human approval
- Jira create nodes then build:
  - Epic
  - parent task
  - subtask

Current behavior:
- the workflow creates only the first task and first subtask path, not a full FR/TC loop

## Key Interfaces

### Incoming chat shape

```json
{
  "chatInput": "text",
  "sessionId": "session-identifier",
  "mode": "analyze"
}
```

### Outgoing response shape consumed by the frontend

```json
{
  "output": "display text",
  "text": "display text",
  "sessionId": "session-identifier",
  "mode": "analyze|generate|complete",
  "action": "continue|generate|done",
  "fullOutput": "full markdown PRD when done",
  "contextSummary": "summarized generation context when needed",
  "qualityScore": 82,
  "grade": "B"
}
```

## External Dependencies

- Ollama
- Gmail
- Jira Software Cloud
- active n8n environment

Use placeholders in docs and operator notes for credentials, account IDs, and project-specific values.

## Workflow-Specific Troubleshooting

- Wrong branch taken: inspect parsed `action`
- Endless questioning: inspect analyze prompt and `GENERATE_PRD:` detection
- Low PRD score: inspect validation patterns versus actual markdown structure
- No attachment email: inspect binary merge and email validation
- No Jira hierarchy: inspect extracted `tasks[0]`, `subtasks[0]`, and Jira create-node mapping
