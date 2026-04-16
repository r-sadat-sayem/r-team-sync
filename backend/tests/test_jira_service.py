from __future__ import annotations

import json

import httpx
import pytest

from src.services.jira import JiraService


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


def _http_400(url: str, errors: dict, messages: list | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    body = json.dumps({"errorMessages": messages or [], "errors": errors}).encode()
    response = httpx.Response(400, request=request, content=body)
    return httpx.HTTPStatusError("bad request", request=request, response=response)


def _make_service() -> JiraService:
    return JiraService(
        base_url="https://api.atlassian.com/ex/jira/test-cloud-id",
        auth_headers={"Authorization": "Bearer fake-token"},
        basic_auth=None,
        project="TSA",
        auth_mode="oauth",
        cloud_url="https://test.atlassian.net",
    )


# ── _post error surfacing ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_surfaces_jira_field_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """_post should raise RuntimeError with Jira's field-level error details."""
    service = _make_service()
    issue_url = f"{service._base_url}/rest/api/3/issue"

    async def fake_request_json(method, path, *, params=None, body=None, timeout=10):
        raise _http_400(issue_url, {"customfield_10011": "Epic Name is required."})

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(RuntimeError, match="customfield_10011: Epic Name is required"):
        await service._post("/rest/api/3/issue", {"fields": {}})


# ── create_epic fallback ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_epic_drops_custom_field_on_team_managed(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    create_epic should retry without customfield_10011 when Jira rejects it
    (team-managed projects don't have that field on the create screen).
    """
    service = _make_service()
    issue_url = f"{service._base_url}/rest/api/3/issue"
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        fields = body["fields"]
        captured.append(dict(fields))
        if "customfield_10011" in fields:
            raise RuntimeError("JIRA 400: customfield_10011: Field 'customfield_10011' does not exist on screen")
        return {"key": "TSA-1"}

    monkeypatch.setattr(service, "_post", fake_post)

    key = await service.create_epic("My Feature", "", None, project="TSA")

    assert key == "TSA-1"
    assert len(captured) == 2, "Expected exactly two attempts"
    assert "customfield_10011" in captured[0], "First attempt should include Epic Name"
    assert "customfield_10011" not in captured[1], "Retry should drop Epic Name"


@pytest.mark.asyncio
async def test_create_epic_succeeds_with_custom_field_on_classic(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_epic should succeed on first try for company-managed projects."""
    service = _make_service()
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        captured.append(dict(body["fields"]))
        return {"key": "TSA-2"}

    monkeypatch.setattr(service, "_post", fake_post)

    key = await service.create_epic("Classic Feature", "Some description", None, project="TSA")

    assert key == "TSA-2"
    assert len(captured) == 1, "Company-managed project should succeed on first try"
    assert captured[0]["customfield_10011"] == "Classic Feature"


# ── create_story fallback ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_story_falls_back_to_epic_link_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    create_story should retry with customfield_10014 when `parent` is rejected
    (classic company-managed projects use the legacy Epic Link field).
    """
    service = _make_service()
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        fields = body["fields"]
        captured.append(dict(fields))
        if "parent" in fields:
            raise RuntimeError("JIRA 400: parent: Field 'parent' cannot be set")
        return {"key": "TSA-3"}

    monkeypatch.setattr(service, "_post", fake_post)

    key = await service.create_story("FR1: Login flow", "TSA-1", None, project="TSA")

    assert key == "TSA-3"
    assert len(captured) == 2
    assert "parent" in captured[0], "First attempt should use parent field"
    assert "parent" not in captured[1], "Retry should drop parent"
    assert captured[1].get("customfield_10014") == "TSA-1", "Retry should set Epic Link"


@pytest.mark.asyncio
async def test_create_story_succeeds_with_parent_on_team_managed(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_story should succeed on first try for team-managed (next-gen) projects."""
    service = _make_service()
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        captured.append(dict(body["fields"]))
        return {"key": "TSA-4"}

    monkeypatch.setattr(service, "_post", fake_post)

    key = await service.create_story("FR1: Feature", "TSA-1", None, project="TSA")

    assert key == "TSA-4"
    assert len(captured) == 1
    assert captured[0]["parent"] == {"key": "TSA-1"}


@pytest.mark.asyncio
async def test_search_projects_falls_back_to_jira_context_path(monkeypatch: pytest.MonkeyPatch) -> None:
    service = JiraService(
        base_url="https://jira.rakuten-it.com",
        auth_headers={},
        basic_auth=("user", "token"),
        project="TSA",
        auth_mode="pat",
        cloud_url="https://jira.rakuten-it.com",
    )

    calls: list[str] = []

    async def fake_request_json(method: str, path: str, *, params=None, body=None, timeout=10):
        url = f"{service._base_url}{path}"
        calls.append(url)
        if service._base_url == "https://jira.rakuten-it.com":
            raise _http_404(url)
        return {"values": [{"id": "1", "key": "TSA", "name": "Team Sync"}], "total": 1}

    async def fake_get(path: str, params=None):
        last_error = None
        original_base = service._base_url
        for candidate in service._base_candidates:
            service._base_url = candidate
            try:
                return await fake_request_json("GET", path, params=params)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code != 404 or candidate == service._base_candidates[-1]:
                    raise
        service._base_url = original_base
        if last_error:
            raise last_error
        return []

    monkeypatch.setattr(service, "_get", fake_get)

    projects = await service.search_projects()

    assert projects == [{"id": "1", "key": "TSA", "name": "Team Sync"}]
    assert calls[0] == "https://jira.rakuten-it.com/rest/api/3/project/search"
    assert calls[1] == "https://jira.rakuten-it.com/jira/rest/api/3/project/search"
    assert service._base_url == "https://jira.rakuten-it.com/jira"


# ── Issue-type resolution ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_subtask_retries_with_sub_task_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When Jira rejects 'Subtask' (400 issuetype), the service should fetch available
    types, resolve 'Subtask' → 'Sub-task' via the alias table, and retry once.
    """
    service = _make_service()
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        fields = body["fields"]
        captured.append(dict(fields))
        if fields.get("issuetype", {}).get("name") == "Subtask":
            raise RuntimeError("JIRA 400: issuetype: Specify a valid issue type")
        return {"key": "TSA-10"}

    async def fake_fetch_issue_types(project_key: str) -> dict:
        return {"story": "Story", "sub-task": "Sub-task", "epic": "Epic"}

    monkeypatch.setattr(service, "_post", fake_post)
    monkeypatch.setattr(service, "fetch_issue_types", fake_fetch_issue_types)

    key = await service.create_subtask("TC001: Core verification", "TSA-5", None, project="TSA")

    assert key == "TSA-10"
    assert len(captured) == 2, "Expected initial attempt + one retry"
    assert captured[0]["issuetype"]["name"] == "Subtask", "First attempt uses configured type"
    assert captured[1]["issuetype"]["name"] == "Sub-task", "Retry uses resolved alias"


@pytest.mark.asyncio
async def test_create_epic_retries_with_resolved_issuetype(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When Jira rejects 'Epic' (400 issuetype), the service resolves to the available
    type and retries.  customfield_10011 drop and issuetype fix can both occur.
    """
    service = _make_service()
    captured: list[dict] = []

    async def fake_post(path: str, body: dict) -> dict:
        fields = body["fields"]
        captured.append(dict(fields))
        if fields.get("issuetype", {}).get("name") == "Epic":
            raise RuntimeError("JIRA 400: issuetype: Specify a valid issue type")
        return {"key": "TSA-20"}

    async def fake_fetch_issue_types(project_key: str) -> dict:
        return {"feature": "Feature", "story": "Story"}

    monkeypatch.setattr(service, "_post", fake_post)
    monkeypatch.setattr(service, "fetch_issue_types", fake_fetch_issue_types)

    key = await service.create_epic("My Feature", "Description", None, project="TSA")

    assert key == "TSA-20"
    assert captured[-1]["issuetype"]["name"] == "Feature"


@pytest.mark.asyncio
async def test_retry_with_resolved_type_raises_when_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When no alias matches the available types, _retry_with_resolved_type should
    raise a descriptive RuntimeError listing the available types.
    """
    service = _make_service()

    # Use types that have NO overlap with the "subtask" alias list so resolution fails.
    async def fake_fetch_issue_types(project_key: str) -> dict:
        return {"incident": "Incident", "change": "Change Request"}

    monkeypatch.setattr(service, "fetch_issue_types", fake_fetch_issue_types)
    fields = {"project": {"key": "TSA"}, "issuetype": {"name": "Subtask"}, "summary": "x"}

    with pytest.raises(RuntimeError, match="Incident"):
        await service._retry_with_resolved_type(fields, "Subtask")


@pytest.mark.asyncio
async def test_search_projects_falls_back_to_latest_project_list(monkeypatch: pytest.MonkeyPatch) -> None:
    service = JiraService(
        base_url="https://jira.example.com/jira",
        auth_headers={},
        basic_auth=("user", "token"),
        project="TSA",
        auth_mode="pat",
        cloud_url="https://jira.example.com/jira",
    )

    async def fake_get(path: str, params=None):
        if path in {"/rest/api/3/project/search", "/rest/api/2/project/search"}:
            raise _http_404(f"https://jira.example.com/jira{path}")
        if path == "/rest/api/latest/project":
            return [{"id": "2", "key": "ABC", "name": "Alpha"}]
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(service, "_get", fake_get)

    projects = await service.search_projects("alp")

    assert projects == [{"id": "2", "key": "ABC", "name": "Alpha"}]


@pytest.mark.asyncio
async def test_create_from_ticket_plan_creates_parent_and_subtasks(monkeypatch: pytest.MonkeyPatch) -> None:
    service = JiraService(
        base_url="https://jira.example.com",
        auth_headers={},
        basic_auth=("user", "token"),
        project="TSA",
        auth_mode="pat",
        cloud_url="https://jira.example.com",
    )
    created_fields: list[dict] = []
    keys = iter(["TSA-100", "TSA-101", "TSA-102"])

    async def fake_create_issue(fields: dict) -> str:
        created_fields.append(fields)
        return next(keys)

    monkeypatch.setattr(service, "_create_issue", fake_create_issue)

    result = await service.create_from_ticket_plan(
        {
            "project_key": "TSA",
            "parent": {
                "issue_type": "Story",
                "summary": "Parent story",
                "description": "Parent description",
            },
            "subtasks": [
                {"summary": "Implement behavior"},
                {"summary": "QA validation"},
            ],
        }
    )

    assert result["parent_key"] == "TSA-100"
    assert result["task_keys"] == ["TSA-101", "TSA-102"]
    assert created_fields[0]["summary"] == "Parent story"
    assert created_fields[0]["issuetype"] == {"name": "Story"}
    assert created_fields[1]["parent"] == {"key": "TSA-100"}
