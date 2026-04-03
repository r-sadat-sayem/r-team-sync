"""
JIRA REST API v3 service.

Creates: Epic → Stories (one per FR) → Subtasks (one per TC per Story).
Assignee is resolved by email → account ID lookup before creating tickets.
All issue types are configurable via env vars.
"""
import logging
import re

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


# ── ADF helpers ───────────────────────────────────────────────────────────────

def _adf(text: str) -> dict:
    """Minimal Atlassian Document Format paragraph for JIRA descriptions."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text[:2000]}],
            }
        ],
    }


# ── PRD extraction ────────────────────────────────────────────────────────────

def extract_jira_items(markdown: str, fallback_name: str = "PRD Feature") -> dict:
    """
    Parse PRD markdown into structured JIRA items.
    Mirrors the logic in the n8n 'Extract JIRA content' Code node.

    Returns:
        {
            "epic_title": str,
            "epic_description": str,     # first 500 chars of Product Overview
            "tasks": [{"id": "FR1", "title": "..."}],   # up to 5
            "subtasks": [{"id": "TC001", "title": "..."}],  # up to 10
        }
    """
    # Epic title — prefer **Project Name** field, fall back to feature name
    proj = re.search(r"\*\*Project Name\*\*[:\s]+([^\n\r]+)", markdown, re.I)
    epic_title = proj.group(1).strip() if proj else fallback_name

    # Epic description — Product Overview section, stripped of bold labels
    overview = re.search(r"#\s*Product Overview([\s\S]*?)(?=\n#|$)", markdown, re.I)
    epic_description = ""
    if overview:
        epic_description = re.sub(r"\*\*[^*]+\*\*\s*:", "", overview.group(1)).strip()[:500]

    # Stories from Functional Requirements (FR1, FR2 …)
    tasks: list[dict] = []
    for m in re.finditer(r"\*\*(FR\d+)\*\*[:\s]+([^\n\r]+)", markdown):
        tasks.append({"id": m.group(1), "title": m.group(2).strip()})
        if len(tasks) >= 5:
            break
    if not tasks:
        tasks = [{"id": "FR1", "title": f"Implement {epic_title}"}]

    # Subtasks from Test Cases (TC001, TC002 …)
    subtasks: list[dict] = []
    for m in re.finditer(r"\*\*(TC\d+)[:\s]+([^*\n\r]+)\*\*", markdown):
        subtasks.append({"id": m.group(1), "title": m.group(2).strip()})
        if len(subtasks) >= 10:
            break
    if not subtasks:
        subtasks = [{"id": "TC001", "title": f"Core feature verification — {epic_title}"}]

    return {
        "epic_title": epic_title,
        "epic_description": epic_description,
        "tasks": tasks,
        "subtasks": subtasks,
    }


# ── JIRA API client ───────────────────────────────────────────────────────────

class JiraService:
    def __init__(self) -> None:
        self.base_url  = settings.jira_base_url.rstrip("/")
        self.auth      = (settings.jira_email, settings.jira_api_token)
        self.headers   = {"Accept": "application/json", "Content-Type": "application/json"}
        self.project   = settings.jira_project_key

    # ── User lookup ───────────────────────────────────────────────────────────

    async def get_account_id(self, email: str) -> str | None:
        """Resolve JIRA account ID from an email address."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/rest/api/3/user/search",
                params={"query": email},
                auth=self.auth,
                headers=self.headers,
                timeout=10,
            )
            r.raise_for_status()
            users = r.json()
            if users:
                logger.debug("Resolved %s → %s", email, users[0]["accountId"])
                return users[0]["accountId"]
            logger.warning("No JIRA user found for email: %s", email)
            return None

    async def get_display_name(self, account_id: str) -> str:
        """Fetch the display name for a JIRA account ID."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/rest/api/3/user",
                params={"accountId": account_id},
                auth=self.auth,
                headers=self.headers,
                timeout=10,
            )
            r.raise_for_status()
            return r.json().get("displayName", account_id)

    # ── Issue creation ────────────────────────────────────────────────────────

    async def _create_issue(self, fields: dict) -> str:
        """POST to /rest/api/3/issue, return new issue key."""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/rest/api/3/issue",
                json={"fields": fields},
                auth=self.auth,
                headers=self.headers,
                timeout=15,
            )
            if not r.is_success:
                logger.error("JIRA create issue failed: %s — %s", r.status_code, r.text)
                r.raise_for_status()
            key = r.json()["key"]
            logger.info("Created JIRA issue: %s", key)
            return key

    async def create_epic(
        self,
        title: str,
        description: str,
        account_id: str | None,
    ) -> str:
        fields: dict = {
            "project":   {"key": self.project},
            "issuetype": {"name": settings.jira_epic_type},
            "summary":   f"[PRD] {title}",
        }
        if description:
            fields["description"] = _adf(description)
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    async def create_story(
        self,
        title: str,
        epic_key: str,
        account_id: str | None,
    ) -> str:
        fields: dict = {
            "project":   {"key": self.project},
            "issuetype": {"name": settings.jira_story_type},
            "summary":   title,
            "parent":    {"key": epic_key},
        }
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    async def create_subtask(
        self,
        title: str,
        parent_key: str,
        account_id: str | None,
    ) -> str:
        fields: dict = {
            "project":   {"key": self.project},
            "issuetype": {"name": settings.jira_subtask_type},
            "summary":   title,
            "parent":    {"key": parent_key},
        }
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    # ── Full PRD → JIRA hierarchy ─────────────────────────────────────────────

    async def create_from_prd(
        self,
        prd_markdown: str,
        feature_name: str,
        assignee_email: str,
    ) -> dict:
        """
        Parse PRD and create the full JIRA hierarchy:
          Epic → Stories (one per FR) → Subtasks (one per TC, under first story)

        Returns:
            {
                "epic_key": "TSA-1",
                "epic_url": "https://...",
                "task_keys": ["TSA-2", "TSA-3"],
                "assignee_name": "...",
            }
        """
        items = extract_jira_items(prd_markdown, feature_name)
        account_id = await self.get_account_id(assignee_email) if assignee_email else None
        assignee_name = ""
        if account_id:
            assignee_name = await self.get_display_name(account_id)

        # Create Epic
        epic_key = await self.create_epic(
            title=items["epic_title"],
            description=items["epic_description"],
            account_id=account_id,
        )
        epic_url = f"{self.base_url}/browse/{epic_key}"

        # Create Stories
        task_keys: list[str] = []
        for task in items["tasks"]:
            key = await self.create_story(
                title=f"{task['id']}: {task['title']}",
                epic_key=epic_key,
                account_id=account_id,
            )
            task_keys.append(key)

        # Create Subtasks under the first story
        if task_keys and items["subtasks"]:
            first_story = task_keys[0]
            for sub in items["subtasks"]:
                await self.create_subtask(
                    title=f"{sub['id']}: {sub['title']}",
                    parent_key=first_story,
                    account_id=account_id,
                )

        logger.info(
            "JIRA hierarchy created: epic=%s tasks=%s assignee=%s",
            epic_key, task_keys, assignee_email,
        )
        return {
            "epic_key":      epic_key,
            "epic_url":      epic_url,
            "task_keys":     task_keys,
            "assignee_name": assignee_name,
        }
