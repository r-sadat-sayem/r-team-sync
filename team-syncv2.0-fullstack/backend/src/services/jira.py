from __future__ import annotations

"""
JIRA REST API v3 service.

Authentication modes (resolved at construction time):

  1. OAuth user token  — preferred
     Loaded from the in-process token store keyed by session_id.
     API base: https://api.atlassian.com/ex/jira/{cloud_id}
     Respects the user's board permissions.

  2. API key fallback  — used when no user has connected via OAuth
     Read from JIRA_EMAIL + JIRA_API_TOKEN in .env.
     API base: JIRA_BASE_URL (e.g. https://your-org.atlassian.net)
     Creates tickets as the service account.

Usage:
    svc = await JiraService.for_user(db, user_id)
    result = await svc.create_from_prd(markdown, feature_name, assignee_email)
"""
import logging
import re
from typing import Dict, List, Optional, Tuple, Union

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.oauth_connections import get_oauth_connection

logger = logging.getLogger(__name__)


# ── ADF helpers ───────────────────────────────────────────────────────────────

def _adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text[:2000]}]}
        ],
    }


# ── PRD extraction ────────────────────────────────────────────────────────────

def extract_jira_items(markdown: str, fallback_name: str = "PRD Feature") -> dict:
    """
    Parse PRD markdown → structured items for JIRA.
    Mirrors n8n 'Extract JIRA content' Code node logic.
    """
    proj = re.search(r"\*\*Project Name\*\*[:\s]+([^\n\r]+)", markdown, re.I)
    epic_title = proj.group(1).strip() if proj else fallback_name

    overview = re.search(r"#\s*Product Overview([\s\S]*?)(?=\n#|$)", markdown, re.I)
    epic_description = ""
    if overview:
        epic_description = re.sub(r"\*\*[^*]+\*\*\s*:", "", overview.group(1)).strip()[:500]

    tasks: list[dict] = []
    for m in re.finditer(r"\*\*(FR\d+)\*\*[:\s]+([^\n\r]+)", markdown):
        tasks.append({"id": m.group(1), "title": m.group(2).strip()})
        if len(tasks) >= 5:
            break
    if not tasks:
        tasks = [{"id": "FR1", "title": f"Implement {epic_title}"}]

    subtasks: list[dict] = []
    for m in re.finditer(r"\*\*(TC\d+)[:\s]+([^*\n\r]+)\*\*", markdown):
        subtasks.append({"id": m.group(1), "title": m.group(2).strip()})
        if len(subtasks) >= 10:
            break
    if not subtasks:
        subtasks = [{"id": "TC001", "title": f"Core feature verification — {epic_title}"}]

    return {
        "epic_title":        epic_title,
        "epic_description":  epic_description,
        "tasks":             tasks,
        "subtasks":          subtasks,
    }


# ── JIRA service ──────────────────────────────────────────────────────────────

class JiraService:

    def __init__(
        self,
        base_url: str,
        auth_headers: dict,
        basic_auth: Optional[Tuple[str, str]],
        project: str,
        auth_mode: str,
        cloud_url: str = "",
    ) -> None:
        self._base_url    = base_url
        self._headers     = {"Accept": "application/json", "Content-Type": "application/json", **auth_headers}
        self._basic_auth  = basic_auth   # None when using OAuth Bearer
        self._project     = project
        self._auth_mode   = auth_mode    # "oauth" | "apikey"
        self._cloud_url   = cloud_url.rstrip("/")

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    async def for_user(cls, db: AsyncSession, user_id: Optional[int]) -> "JiraService":
        """
        Build the right JiraService for the given user.

        If the user has a connected OAuth token → use it (user-level access).
        Otherwise → fall back to API key from .env (service account).
        """
        token = await get_oauth_connection(db, user_id, "jira") if user_id else None

        if token:
            base_url = f"https://api.atlassian.com/ex/jira/{token.cloud_id}"
            return cls(
                base_url=base_url,
                auth_headers={"Authorization": f"Bearer {token.access_token}"},
                basic_auth=None,
                project=settings.jira_project_key,
                auth_mode="oauth",
                cloud_url=token.cloud_url,
            )

        # Second fallback — user-supplied PAT credentials stored in DB
        pat = await get_oauth_connection(db, user_id, "jira_pat") if user_id else None
        if pat:
            project = pat.cloud_id or settings.jira_project_key
            return cls(
                base_url=pat.cloud_url.rstrip("/"),
                auth_headers={},
                basic_auth=(pat.account_email, pat.access_token),
                project=project,
                auth_mode="pat",
                cloud_url=pat.cloud_url,
            )

        # Final fallback — .env service account
        if not settings.jira_base_url or not settings.jira_api_token:
            raise RuntimeError(
                "No JIRA credentials available. "
                "Either connect via OAuth, save a Personal Access Token in the JIRA tab, "
                "or set JIRA_BASE_URL + JIRA_EMAIL + JIRA_API_TOKEN in .env"
            )
        base = settings.jira_base_url.rstrip("/")
        # Jira Cloud (*.atlassian.net) uses Basic auth: email + API token.
        # Jira Server / Data Center uses Bearer PAT auth.
        is_cloud = "atlassian.net" in base
        if is_cloud:
            auth_headers: dict = {}
            basic_auth: Optional[Tuple[str, str]] = (settings.jira_email, settings.jira_api_token)
        else:
            auth_headers = {"Authorization": f"Bearer {settings.jira_api_token}"}
            basic_auth = None
        return cls(
            base_url=base,
            auth_headers=auth_headers,
            basic_auth=basic_auth,
            project=settings.jira_project_key,
            auth_mode="apikey",
        )

    # ── URL helpers ───────────────────────────────────────────────────────────

    def _browse_url(self, key: str) -> str:
        """Return the Jira browse URL for an issue key, using the correct base."""
        base = self._cloud_url if self._cloud_url else self._base_url
        return f"{base.rstrip('/')}/browse/{key}"

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _client_kwargs(self) -> dict:
        kwargs: dict = {"headers": self._headers}
        if self._basic_auth:
            kwargs["auth"] = self._basic_auth
        return kwargs

    async def _get(self, path: str, params: Optional[dict] = None) -> Union[Dict, List]:
        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            r = await client.get(
                f"{self._base_url}{path}",
                params=params,
                timeout=10,
            )
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            r = await client.post(
                f"{self._base_url}{path}",
                json=body,
                timeout=15,
            )
            if not r.is_success:
                logger.error("JIRA POST %s failed %s: %s", path, r.status_code, r.text)
                r.raise_for_status()
            return r.json()

    # ── User lookup ───────────────────────────────────────────────────────────

    async def get_account_id(self, email: str) -> Optional[str]:
        """Resolve JIRA account ID from an email address."""
        users = await self._get("/rest/api/3/user/search", params={"query": email})
        if isinstance(users, list) and users:
            logger.debug("Resolved %s → %s", email, users[0]["accountId"])
            return users[0]["accountId"]
        logger.warning("No JIRA user found for email: %s", email)
        return None

    async def get_display_name(self, account_id: str) -> str:
        data = await self._get("/rest/api/3/user", params={"accountId": account_id})
        return data.get("displayName", account_id)

    # ── Issue creation ────────────────────────────────────────────────────────

    async def _create_issue(self, fields: dict) -> str:
        data = await self._post("/rest/api/3/issue", {"fields": fields})
        key = data["key"]
        logger.info("Created JIRA issue [%s]: %s", self._auth_mode, key)
        return key

    async def create_epic(self, title: str, description: str, account_id: Optional[str], project: str = "") -> str:
        fields: dict = {
            "project":   {"key": project or self._project},
            "issuetype": {"name": settings.jira_epic_type},
            "summary":   f"[PRD] {title}",
        }
        if description:
            fields["description"] = _adf(description)
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    async def create_story(self, title: str, epic_key: str, account_id: Optional[str], project: str = "") -> str:
        fields: dict = {
            "project":   {"key": project or self._project},
            "issuetype": {"name": settings.jira_story_type},
            "summary":   title,
            "parent":    {"key": epic_key},
        }
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    async def create_subtask(self, title: str, parent_key: str, account_id: Optional[str], project: str = "") -> str:
        fields: dict = {
            "project":   {"key": project or self._project},
            "issuetype": {"name": settings.jira_subtask_type},
            "summary":   title,
            "parent":    {"key": parent_key},
        }
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        return await self._create_issue(fields)

    # ── Board & project discovery ─────────────────────────────────────────────

    async def fetch_all_boards(self, project_key: Optional[str] = None) -> List[dict]:
        """Fetch all Agile boards, paginating until isLast is True.
        Pass project_key to filter boards belonging to a specific project.
        """
        boards: list[dict] = []
        start_at = 0
        base_params: dict = {"maxResults": 50}
        if project_key:
            base_params["projectKeyOrId"] = project_key
        while True:
            data = await self._get(
                "/rest/agile/1.0/board",
                params={"startAt": start_at, **base_params},
            )
            values = data.get("values", [])
            boards.extend(values)
            if data.get("isLast", True):
                break
            start_at += len(values)
        logger.debug("fetch_all_boards: returned %d boards", len(boards))
        return boards

    async def search_projects(self, query: str = "") -> List[dict]:
        """
        Return all visible projects, optionally filtered by name or key.

        Uses /rest/api/2/project — compatible with both Jira Server and Cloud.
        Filtering is done locally (case-insensitive substring match).
        """
        all_projects: list[dict] = await self._get("/rest/api/2/project")
        if not query:
            return all_projects
        q = query.lower()
        return [
            p for p in all_projects
            if q in p.get("name", "").lower() or q in p.get("key", "").lower()
        ]

    # ── Full PRD → JIRA hierarchy ─────────────────────────────────────────────

    async def create_from_prd(
        self,
        prd_markdown: str,
        feature_name: str,
        assignee_email: str,
        project_key: str = "",
    ) -> dict:
        """
        Epic → Stories (all FRs) → Subtasks (all TCs under each story).

        project_key overrides self._project when non-empty.
        Returns: {epic_key, epic_url, task_keys, assignee_name, auth_mode, cloud_url}
        """
        proj       = project_key or self._project
        items      = extract_jira_items(prd_markdown, feature_name)
        account_id = await self.get_account_id(assignee_email) if assignee_email else None
        assignee_name = ""
        if account_id:
            assignee_name = await self.get_display_name(account_id)

        epic_key = await self.create_epic(
            title=items["epic_title"],
            description=items["epic_description"],
            account_id=account_id,
            project=proj,
        )

        task_keys: list[str] = []
        for task in items["tasks"]:
            key = await self.create_story(
                title=f"{task['id']}: {task['title']}",
                epic_key=epic_key,
                account_id=account_id,
                project=proj,
            )
            task_keys.append(key)

            for sub in items["subtasks"]:
                await self.create_subtask(
                    title=f"{sub['id']}: {sub['title']}",
                    parent_key=key,
                    account_id=account_id,
                    project=proj,
                )

        logger.info(
            "JIRA hierarchy created [%s]: epic=%s stories=%d assignee=%s",
            self._auth_mode, epic_key, len(task_keys), assignee_email,
        )
        return {
            "epic_key":      epic_key,
            "epic_url":      self._browse_url(epic_key),
            "task_keys":     task_keys,
            "assignee_name": assignee_name,
            "auth_mode":     self._auth_mode,
            "cloud_url":     self._cloud_url,
        }
