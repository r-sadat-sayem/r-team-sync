# ACL + Integration Center Plan

> Detailed implementation plan for:
> 1. Internal access control over agent tool usage
> 2. Unified user-managed tool connections via OAuth
> Date: 2026-04-15

---

## Feasibility Verdict

**Architecture verdict: high-value**

This feature set fits the current application well because the repo already has:

- account-based app authentication
- per-user OAuth token storage
- separate backend service modules for external tools
- a frontend navigation structure that can absorb a central integrations surface

The current gap is not identity. The gap is policy. Today, once a user connects JIRA or Gmail, the application has no internal permission layer that decides what the agent may or may not do with that connection. This plan closes that gap first, then standardizes future tool onboarding.

---

## Why this work matters

Current behavior:

- users authenticate into TeamSync
- users connect Gmail and JIRA with OAuth
- backend stores those tokens per user
- agent actions are mostly governed by provider scopes and hard-coded app flows

Current limitations:

- there is no app-managed ACL between "OAuth connected" and "agent can act"
- integrations are represented as separate task pages instead of one control center
- provider auth logic is duplicated by tool
- future tools like Slack, Confluence, Outlook, and Teams would add more one-off code if built on the current pattern

Desired future behavior:

- users connect tools in one place
- users explicitly decide what powers the agent has for each tool
- the backend blocks or pauses agent actions based on app policy, not just provider scope
- new integrations can plug into a shared auth and access model

---

## Scope

### In scope for this planning document

- internal ACL for external tool actions
- Integration Center UI
- standard user-to-tool OAuth lifecycle
- migration of current JIRA and Gmail flows onto the new model
- backend and frontend interfaces needed for future providers

### Out of scope for the first implementation

- org-wide RBAC and admin role management
- SCIM, SSO policy sync, or directory-driven permissions
- arbitrary public MCP server marketplace
- app-only service-account automation as the default path
- full implementation of Slack, Confluence, Outlook, or Teams

Those future providers are part of the architecture target, but JIRA and Gmail are the first migration targets.

---

## Product goals

1. Users can manage all tool connections from one place.
2. OAuth connection status and agent authority are clearly separated in the UI.
3. The backend evaluates policy before any external write action executes.
4. JIRA and Gmail stop being special cases and become the first providers on a shared integration model.
5. Future providers can be added without redesigning auth or permission storage.

## Non-goals

1. Replace provider-side permissions with app-side permissions.
2. Grant the agent access beyond the user’s real provider scopes.
3. Build full enterprise admin governance in the first phase.

---

## Working assumptions

- This is an internal enterprise tool with per-user delegated OAuth.
- The primary grouping model is by integration section in the UI, not by organization role.
- Safe defaults are required:
  - read/list/search actions default to allowed
  - create/update/send actions default to ask or disabled
  - delete/admin/destructive actions default to denied
- Existing `oauth_connections` should remain the credential store for backward compatibility.
- Existing JIRA and Gmail flows must keep working while the new system is introduced.

---

## Current-state grounding

Relevant current backend pieces:

- `backend/src/models.py`
  - `User`, `AuthSession`, `AppSession`, `OAuthConnection`
- `backend/src/services/oauth_connections.py`
  - basic token get/upsert/delete helpers
- `backend/src/routers/jira_auth.py`
  - JIRA OAuth and JIRA user-scoped actions
- `backend/src/routers/email_auth.py`
  - Gmail OAuth connect/status/disconnect
- `backend/src/graph/nodes.py`
  - hard-coded JIRA and email action nodes

Relevant current frontend pieces:

- `frontend/src/components/layout/Sidebar.tsx`
  - no central integrations page yet
- `frontend/src/App.tsx`
  - separate `Email` and `JIRA` pages
- `frontend/src/services/api.ts`
  - tool-specific auth methods

Key current architectural fact:

- OAuth tokens are stored per user
- policy is not stored per user/provider/capability
- graph nodes can directly trigger tool actions once the flow reaches them

That last point is the core design problem this plan addresses.

---

## Proposed solution overview

Introduce three new layers:

1. **Integration Catalog**
   - code-defined registry of supported providers and capabilities

2. **Access Policy Layer**
   - per-user rules that decide whether the agent may perform a capability

3. **Integration Center**
   - a unified frontend surface for connection status, OAuth metadata, and access controls

The execution model becomes:

1. User logs in to TeamSync
2. User connects a provider via OAuth
3. TeamSync stores provider token + metadata
4. User configures agent access policy for that provider
5. Agent attempts an action
6. Backend checks:
   - is provider connected?
   - does provider scope support the action?
   - does TeamSync policy allow the action?
7. Backend either:
   - runs the action
   - pauses for approval
   - blocks with a clear denial reason

---

## Information architecture for the UI

Add a new primary page:

- `Integrations & Access`

Recommended sections:

- `Work Management`
  - JIRA
  - Confluence
- `Communication`
  - Gmail
  - Outlook
  - Slack
  - Teams
- `AI / Tooling`
  - MCP Servers

### Card structure per integration

Each provider card should show:

- provider name and logo/icon
- connection state
- connected user/account/workspace
- granted OAuth scopes
- capability-level access controls
- last sync / last auth issue
- missing scope or permission warning if relevant

### Key UX rule

Visually separate:

- **Provider Access**
  - what OAuth granted
- **Agent Access**
  - what TeamSync is allowed to do

This distinction prevents users from assuming that connecting a tool automatically means the agent can act freely.

### Recommended control model

For each capability, offer:

- `Allow`
- `Ask`
- `Deny`

Suggested defaults:

- read-like capabilities: `Allow`
- write/send/update capabilities: `Ask`
- destructive or administrative capabilities: `Deny`

---

## Capability model

Use stable capability identifiers that are provider-specific but consistently shaped.

Examples:

- `gmail.send`
- `jira.project.read`
- `jira.issue.create`
- `jira.issue.update`
- `jira.issue.comment`
- `slack.channel.read`
- `slack.message.send`
- `confluence.page.read`
- `confluence.page.create`
- `outlook.mail.send`
- `teams.message.send`

Capability metadata should include:

- `provider`
- `section`
- `label`
- `description`
- `risk_level`
- `default_mode`
- `required_scopes`
- `requires_confirmation`
- `is_destructive`

This catalog should live in backend code, not in the database, so the product has a canonical source of truth for supported behaviors.

---

## Data model changes

### Keep existing table

Keep `oauth_connections` as the main token store.

### Extend `oauth_connections`

Add fields needed for a shared provider model:

- `scopes` as serialized string or JSON
- `provider_account_id`
- `workspace_id`
- `workspace_name`
- `token_expires_at`
- `last_validated_at`
- `status`
- `status_message`

Purpose:

- support richer UI status
- support provider diagnostics
- support future providers without overloading `cloud_*` as JIRA-only semantics

### Add new table: `integration_policies`

Proposed fields:

- `id`
- `user_id`
- `provider`
- `capability`
- `mode` (`allow` | `ask` | `deny`)
- `updated_at`

Constraint:

- unique on `user_id + provider + capability`

### Optional later table: `integration_approval_events`

Not required for the first cut, but useful if audit history becomes important.

Potential fields:

- `id`
- `user_id`
- `session_id`
- `provider`
- `capability`
- `decision`
- `reason`
- `created_at`

---

## Backend architecture changes

## 1. Integration catalog module

Add a backend module such as:

- `backend/src/services/integration_catalog.py`

Responsibilities:

- define all supported providers
- define supported capabilities per provider
- map capabilities to required OAuth scopes
- expose default policy modes
- drive both backend validation and frontend rendering

This should be static application metadata, not dynamic user data.

## 2. Access policy service

Add:

- `backend/src/services/access_policy.py`

Responsibilities:

- fetch effective policy for a user/provider/capability
- supply defaults when no record exists
- determine action result:
  - `allow`
  - `ask`
  - `deny`
- produce structured denial reasons
- detect mismatches between requested capability and granted OAuth scopes

Example result object:

```python
{
    "decision": "allow" | "ask" | "deny",
    "reason": "missing_scope" | "policy_denied" | "approval_required" | None,
    "message": "Human-readable explanation"
}
```

## 3. Shared OAuth helper layer

Current provider auth logic is duplicated between JIRA and Gmail.

Add a shared helper module such as:

- `backend/src/services/provider_oauth.py`

Responsibilities:

- generate connect URL
- exchange auth code for tokens
- refresh access token
- normalize provider profile/workspace metadata
- store connection status

Keep provider-specific logic in provider adapters, but move the lifecycle skeleton into shared code.

## 4. Provider adapters

Introduce per-provider adapters with a common shape.

Examples:

- `backend/src/services/providers/jira_provider.py`
- `backend/src/services/providers/gmail_provider.py`

Responsibilities:

- provider-specific auth parameters
- profile/status resolution
- supported capabilities
- tool operations
- scope mapping

## 5. Enforce policy before side effects

This is the most important backend rule.

No external write operation should execute until policy is checked.

Enforcement points:

- JIRA ticket creation
- JIRA updates or comments when added later
- email sending
- future Slack/Teams/Confluence writes

Recommended pattern:

1. graph node requests capability
2. access policy service evaluates user + provider + capability
3. if `allow`: execute service call
4. if `ask`: emit interrupt payload for approval
5. if `deny`: return structured blocked event

## 6. Introduce integration routers

Add new routers:

- `backend/src/routers/integrations.py`
- `backend/src/routers/access_policies.py`

Recommended endpoints:

- `GET /api/v1/integrations/catalog`
- `GET /api/v1/integrations`
- `GET /api/v1/integrations/{provider}/status`
- `POST /api/v1/integrations/{provider}/connect`
- `DELETE /api/v1/integrations/{provider}/disconnect`
- `GET /api/v1/access-policies`
- `PUT /api/v1/access-policies/{provider}`

JIRA and Gmail legacy endpoints can stay temporarily, but should be treated as compatibility routes that eventually delegate to the new services.

---

## LangGraph and workflow changes

Current graph nodes directly manage email and JIRA branching in a task-specific way.

### Required changes

1. Before `send_email`, evaluate `gmail.send`
2. Before `create_jira`, evaluate `jira.issue.create`
3. If policy result is `ask`, emit a new interrupt type
4. On approval resume, continue execution
5. On denial, surface a clean event back to the UI

### New event types

- `access_approval_required`
- `access_denied`
- `integration_status_changed`

### Why this matters

This keeps the graph as the orchestration layer while moving authorization decisions into reusable policy services.

---

## Frontend architecture changes

## 1. Add Integration Center route

Add a route such as:

- `/integrations`

Update sidebar navigation to include:

- `Integrations & Access`

Keep `/email` and `/jira` temporarily, but shift them toward:

- deep-link views into the new shared integrations experience
- or compatibility pages that use shared APIs and shared status cards

## 2. New frontend state and types

Add types for:

- `IntegrationProvider`
- `IntegrationCapability`
- `IntegrationStatus`
- `AccessPolicy`
- `AccessDecision`

Frontend data should no longer be JIRA- or Gmail-specific at the page shell level.

## 3. Build reusable integration card components

Recommended components:

- `IntegrationSection`
- `IntegrationCard`
- `CapabilityToggleGroup`
- `ConnectionStatusBadge`
- `MissingScopeAlert`

## 4. Approval UX

When a graph action returns `access_approval_required`, show a lightweight modal or inline interrupt card with:

- integration name
- requested action
- reason for approval
- allow once / deny once behavior for the current run

This approval UX is distinct from persistent policy editing in the Integration Center.

## 5. Status messaging

The UI should clearly distinguish:

- not connected
- connected but missing required scopes
- connected and policy-denied
- connected and approval-required
- connected and ready

---

## Public API contract draft

## Integration catalog

`GET /api/v1/integrations/catalog`

Returns:

- sections
- providers
- capability definitions
- default modes

## User integration list

`GET /api/v1/integrations`

Returns user-specific status for each provider:

- connected
- account/workspace metadata
- granted scopes
- health/status message
- effective capability modes

## Policy update

`PUT /api/v1/access-policies/{provider}`

Request body example:

```json
{
  "capabilities": [
    { "capability": "jira.issue.create", "mode": "allow" },
    { "capability": "jira.issue.update", "mode": "deny" },
    { "capability": "jira.issue.comment", "mode": "ask" }
  ]
}
```

## Integration status

`GET /api/v1/integrations/{provider}/status`

Returns:

- connection status
- account metadata
- granted scopes
- missing required scopes by capability

---

## Migration plan

### Phase 1: Foundations

- define integration catalog
- add policy storage
- add access policy service
- create new integration and policy APIs
- add Integration Center page shell in frontend

Done when:

- a user can see JIRA and Gmail in the Integration Center
- policies can be viewed and updated
- no provider logic is yet removed

### Phase 2: Migrate existing providers

- move Gmail flow onto shared integration status and policy checks
- move JIRA flow onto shared integration status and policy checks
- add policy enforcement before `send_email` and `create_jira`
- support approval interrupts for `ask`

Done when:

- current email and JIRA flows still work
- policy can block or pause those actions

### Phase 3: Polish and provider-readiness

- remove duplicated UI logic between old pages and Integration Center
- improve scope diagnostics and error messages
- document how new providers should be added
- expose generic provider status cards for future Slack/Outlook/Confluence/Teams work

Done when:

- Gmail and JIRA are first-class providers on the new system
- adding the next provider is an adapter task, not an architecture redesign

---

## Testing strategy

## Backend tests

Add tests for:

- default policy resolution when no explicit record exists
- explicit `allow`, `ask`, and `deny` evaluation
- missing-scope detection
- JIRA create blocked by deny policy
- email send blocked by deny policy
- graph interrupt emitted for ask policy
- legacy JIRA/Gmail endpoints still returning compatible data during migration

## Frontend tests

Add tests for:

- Integration Center renders grouped provider sections
- policy controls display current effective modes
- status UI handles not connected / missing scope / denied / ask states
- approval UI appears when a tool action requires approval

## Manual validation scenarios

1. Connect Gmail and set `gmail.send = deny`
   - PRD generation succeeds
   - send step is blocked cleanly

2. Connect JIRA and set `jira.issue.create = ask`
   - PRD flow reaches JIRA stage
   - user receives an approval prompt before ticket creation

3. Connect JIRA but with missing scope or invalid token
   - Integration Center shows degraded status
   - UI explains why JIRA create is unavailable

4. Disconnect a provider
   - Integration Center updates immediately
   - agent actions no longer proceed for that provider

---

## Documentation deliverables

Once implementation begins, documentation should include:

- operator setup guide for provider OAuth apps
- user guide for the Integration Center
- capability matrix by provider
- provider onboarding checklist for future integrations

Recommended future docs:

- `docs/integration-provider-guide.md`
- `docs/integration-operator-setup.md`
- `docs/access-policy-reference.md`

---

## Risks and tradeoffs

## 1. Backward compatibility risk

The current JIRA and Gmail flows are already working. The migration should wrap them with policy checks first, not rewrite everything at once.

## 2. Scope confusion risk

Users may think app policy can override provider permissions. The UI must explicitly show that:

- provider scopes are the upper bound
- TeamSync ACL is the internal lower bound

## 3. Over-generalization risk

Do not build a giant plugin framework in the first pass. The first target is a clean shared pattern for JIRA and Gmail, not a universal integration engine for every future provider.

## 4. Approval fatigue risk

If too many capabilities default to `ask`, the product will become noisy. Use `ask` for meaningful write operations, not for harmless reads.

---

## Recommended implementation order

1. Add integration catalog and policy data model
2. Add backend access policy service
3. Add integration and policy APIs
4. Add Integration Center UI route and shared components
5. Apply policy checks to Gmail flow
6. Apply policy checks to JIRA flow
7. Move old pages onto shared integration APIs
8. Document provider onboarding for the next tools

---

## Success criteria

This phase is successful when:

- users can see all supported integrations in one place
- users can manage agent permissions per integration capability
- OAuth connection and app permission are clearly separated
- Gmail and JIRA actions are enforced through app policy before execution
- the system is ready to onboard the next OAuth-based provider without new authorization architecture
