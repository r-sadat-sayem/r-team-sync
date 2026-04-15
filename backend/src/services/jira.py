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
import asyncio
import logging
import re
from urllib.parse import urlparse
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
        self._base_candidates = self._build_base_candidates(base_url)

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
            project  = pat.cloud_id or settings.jira_project_key
            pat_base = pat.cloud_url.rstrip("/")
            # refresh_token stores the verified auth method: "bearer" | "basic" | ""
            # "bearer" → PAT on SSO/LDAP Jira (Basic auth disabled)
            # "basic"  → username:password or username:PAT with Basic auth enabled
            # ""       → legacy record saved before probe; default to Basic
            if pat.refresh_token == "bearer":
                pat_auth_headers: dict                    = {"Authorization": f"Bearer {pat.access_token}"}
                pat_basic_auth: Optional[Tuple[str, str]] = None
            else:
                pat_auth_headers  = {}
                pat_basic_auth    = (pat.account_email, pat.access_token)
            return cls(
                base_url=pat_base,
                auth_headers=pat_auth_headers,
                basic_auth=pat_basic_auth,
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

    @staticmethod
    def _build_base_candidates(base_url: str) -> List[str]:
        """
        Build candidate Jira bases for self-hosted instances.

        Some deployments serve Jira under `/jira` even when users enter the host root.
        Keep the original base first, then try the `/jira` context path as a fallback.
        """
        normalized = base_url.rstrip("/")
        candidates = [normalized]
        parsed = urlparse(normalized)
        path = parsed.path.rstrip("/")
        if normalized and path in {"", "/"} and not normalized.endswith("/jira"):
            candidates.append(f"{normalized}/jira")
        return candidates

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _client_kwargs(self) -> dict:
        kwargs: dict = {"headers": self._headers}
        if self._basic_auth:
            kwargs["auth"] = self._basic_auth
        return kwargs

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        timeout: int = 10,
    ) -> Union[Dict, List]:
        """
        Issue a Jira request against known base candidates.

        Retry 404s against an alternate `/jira` context path for self-hosted installs.
        When a fallback succeeds, keep that base for later requests.
        """
        last_error: Optional[Exception] = None
        method_name = method.upper()
        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            for candidate in self._base_candidates:
                try:
                    response = await client.request(
                        method_name,
                        f"{candidate}{path}",
                        params=params,
                        json=body,
                        timeout=timeout,
                    )
                    response.raise_for_status()
                    if candidate != self._base_url:
                        logger.info("Resolved Jira base URL fallback: %s -> %s", self._base_url, candidate)
                        self._base_url = candidate
                        self._base_candidates = self._build_base_candidates(candidate)
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if exc.response.status_code != 404 or candidate == self._base_candidates[-1]:
                        raise
                except Exception as exc:
                    last_error = exc
                    raise
        if last_error:
            raise last_error
        raise RuntimeError("JIRA request failed without a response")

    async def _get(self, path: str, params: Optional[dict] = None) -> Union[Dict, List]:
        return await self._request_json("GET", path, params=params, timeout=10)

    async def _post(self, path: str, body: dict) -> dict:
        try:
            data = await self._request_json("POST", path, body=body, timeout=15)
        except httpx.HTTPStatusError as exc:
            logger.error("JIRA POST %s failed %s: %s", path, exc.response.status_code, exc.response.text)
            raise
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected JIRA response payload for POST {path}")
        return data

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
        delays = [0.5, 1.0]
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                data = await self._post("/rest/api/3/issue", {"fields": fields})
                key = data["key"]
                logger.info("Created JIRA issue [%s]: %s", self._auth_mode, key)
                return key
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                logger.warning(
                    "JIRA create_issue attempt %d/3 network error — retrying: %s",
                    attempt + 1, exc,
                )
                if attempt < len(delays):
                    await asyncio.sleep(delays[attempt])
        raise last_exc  # type: ignore[misc]

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

        Jira deployments vary here:
        - some expose `/rest/api/3/project/search`
        - others only support `/rest/api/latest/project` or `/rest/api/2/project`
        - some self-hosted installs require the `/jira` context path
        """
        all_projects: list[dict] = await self._fetch_projects(query=query)
        if not query:
            return all_projects
        q = query.lower()
        return [
            p for p in all_projects
            if q in p.get("name", "").lower() or q in p.get("key", "").lower()
        ]

    async def _fetch_projects(self, query: str = "") -> List[dict]:
        search_candidates = [
            ("/rest/api/3/project/search", {"query": query, "startAt": 0, "maxResults": 100}),
            ("/rest/api/2/project/search", {"query": query, "startAt": 0, "maxResults": 100}),
        ]
        list_candidates = [
            ("/rest/api/latest/project", None),
            ("/rest/api/2/project", None),
        ]

        last_error: Optional[Exception] = None
        for path, params in search_candidates:
            try:
                projects = await self._fetch_projects_from_search_endpoint(path, params or {})
                if projects is not None:
                    return projects
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code != 404:
                    raise

        for path, params in list_candidates:
            try:
                data = await self._get(path, params=params)
                if isinstance(data, list):
                    return data
                raise RuntimeError(f"Unexpected JIRA response payload for GET {path}")
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code != 404:
                    raise

        if last_error:
            raise last_error
        return []

    async def _fetch_projects_from_search_endpoint(self, path: str, params: dict) -> Optional[List[dict]]:
        projects: list[dict] = []
        start_at = 0
        while True:
            data = await self._get(path, params={**params, "startAt": start_at})
            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected JIRA response payload for GET {path}")
            values = data.get("values", [])
            if not isinstance(values, list):
                raise RuntimeError(f"Unexpected JIRA project search payload for GET {path}")
            projects.extend(values)
            total = data.get("total")
            if not values or total is None or len(projects) >= int(total):
                return projects
            start_at += len(values)

    # ── Full PRD → JIRA hierarchy ─────────────────────────────────────────────

    async def create_from_prd(
        self,
        prd_markdown: str,
        feature_name: str,
        assignee_email: str,
        project_key: str = "",
        progress_cb=None,
    ) -> dict:
        """
        Epic → Stories (all FRs) → Subtasks (all TCs under each story).

        project_key overrides self._project when non-empty.
        progress_cb: optional callable(current: int, total: int) called before each story.
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
        total_stories = len(items["tasks"])
        for i, task in enumerate(items["tasks"]):
            if progress_cb:
                progress_cb(i + 1, total_stories)
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
