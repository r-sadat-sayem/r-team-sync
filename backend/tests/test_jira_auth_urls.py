from src.config import settings
from src.routers.jira_auth import _public_jira_base_url


def test_public_jira_base_url_prefers_configured_context_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "jira_base_url", "https://jira.rakuten-it.com/jira")

    assert _public_jira_base_url("https://jira.rakuten-it.com") == "https://jira.rakuten-it.com/jira"


def test_public_jira_base_url_falls_back_when_config_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "jira_base_url", "")

    assert _public_jira_base_url("https://jira.rakuten-it.com/jira") == "https://jira.rakuten-it.com/jira"
