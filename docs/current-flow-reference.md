# Current Flow Reference

## Summary

The active workflow is a dual-mode n8n agent pipeline:

1. Collect requirements conversationally
2. Switch to PRD generation when enough context exists
3. Score the generated PRD
4. Pause for email recipient input
5. Pause for Jira approval
6. Create one Epic, one Task, and one Subtask from the generated PRD

## Inputs

### Chat request payload

The live chat path expects:

```json
{
  "chatInput": "user message",
  "sessionId": "stable-session-key",
  "mode": "analyze"
}
```

`mode` later becomes `generate` when the workflow loops back to produce the final PRD.

## End-to-End Stages

### 1. Conversation intake

- Triggered through the chat webhook
- The workflow uses a session-based memory buffer keyed by `sessionId`
- Analyze mode uses the Sam persona to gather missing requirements
- The agent is instructed to stop once enough information is available

Success signal:
- The assistant returns either another conversational response or a structured `GENERATE_PRD:` summary

Failure modes:
- missing or unstable `sessionId`
- Ollama unavailable
- chat webhook inactive

### 2. Analyze-to-generate handoff

- The workflow parses the agent output
- When it detects the `GENERATE_PRD:` structure, it extracts a compact context summary
- The workflow loops back into itself with `mode=generate`

Success signal:
- The next call is made with generate mode plus `contextSummary`

Failure modes:
- malformed or placeholder context
- summary too weak to support generation

### 3. PRD generation

- Generate mode swaps to the DevBridge PRD generator prompt
- The response is expected to be a full markdown PRD in one output
- Required sections include classification, overview, goals, functional requirements, non-functional requirements, scope, success metrics, and test cases

Success signal:
- The workflow emits `action: "done"` with `fullOutput`

Failure modes:
- model timeout
- incomplete markdown
- low-quality PRD structure

### 4. PRD validation

- The `Validate PRD Quality` code node scores the output from 0 to 100
- Score inputs include:
  - required section detection
  - test case count
  - output length

Success signal:
- returns `qualityScore`, `grade`, `summary`, and section/test metadata

Failure modes:
- weak input produces low score
- missing sections reduce grade sharply

### 5. Binary conversion and email wait

- The markdown is cleaned of `<think>` tags
- The PRD is base64-encoded into a markdown binary payload
- A wait-form URL is generated for recipient entry
- The workflow pauses at the email form until the form is submitted

Success signal:
- user submits name and email
- workflow resumes with both form data and PRD binary available

Failure modes:
- stale wait link
- invalid email
- missing binary when the execution resumes

### 6. Email delivery

- Resumed form data and PRD binary are merged
- Input is validated
- The Gmail node sends the markdown document as an attachment

Success signal:
- email send node completes
- workflow returns a success message

Failure modes:
- Gmail auth expired
- invalid email format
- missing attachment data

### 7. Jira extraction and approval wait

- In parallel with the post-validation path, the workflow extracts:
  - project name for the Epic title
  - product overview for the Epic description
  - first functional requirements as candidate tasks
  - first test cases as candidate subtasks
- A second wait form pauses execution for Jira approval

Success signal:
- approval form is submitted with an approval decision

Failure modes:
- extracted PRD content too sparse
- Jira approval form not completed

### 8. Jira creation

- The Epic is created first
- The first task is created as a child of the Epic
- The first subtask is created as a child of the task

Current scope:
- one Epic
- one Task based on the first FR
- one Subtask based on the first TC

Failure modes:
- Jira auth failure
- project field mismatch
- board configuration mismatch for parent linking

## Observable Outputs

### User-visible

- conversational responses
- a PRD quality score
- email recipient form URL
- Jira approval form URL
- Jira hierarchy in the target project

### Data artifacts

- markdown PRD content
- derived binary markdown attachment
- extracted Epic/task/subtask candidate data

## State and Resume Points

- Conversation continuity depends on `sessionId`
- Email flow pauses at the recipient wait node
- Jira flow pauses at the approval wait node
- Resume links are execution-specific and should not be treated as durable URLs

## Main Debug Entry Points

- Chat does not respond: verify chat webhook and Ollama availability
- PRD never completes: inspect generate-mode prompt and final output shape
- Email path fails: inspect binary conversion, merge, and email validation nodes
- Jira path fails: inspect extracted markdown fields, approval wait, and Jira create nodes
