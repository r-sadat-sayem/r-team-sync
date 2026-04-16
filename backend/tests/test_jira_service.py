import httpx
import pytest

from src.services.jira import JiraService


def _http_404(url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


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
