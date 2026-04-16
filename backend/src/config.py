from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    debug: bool = False
    log_level: str = "info"
    frontend_url: str = "http://localhost:5173"

    # Database — LangGraph checkpointer + app tables share one DB
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # Auth
    auth_cookie_name: str = "teamsync_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_session_days: int = 14
    google_oauth_state_cookie_name: str = "teamsync_google_oauth_state"

    # Rakuten AI Gateway — Anthropic (Claude)
    rakuten_ai_gateway_key: str = ""
    rakuten_anthropic_base_url: str = "https://api.ai.public.rakuten-it.com/anthropic/"
    rakuten_anthropic_model: str = "claude-3-7-sonnet-20250219"

    # Google Login OAuth 2.0 (app login)
    # Setup: console.cloud.google.com → Credentials → OAuth 2.0 Client ID (Web)
    # Callback URL: http://localhost:8000/api/v1/auth/google/callback
    # Scopes: openid email profile
    google_login_client_id: str = ""
    google_login_client_secret: str = ""

    # Gmail OAuth 2.0 (preferred — user logs in via popup)
    # Setup: console.cloud.google.com → Enable Gmail API → OAuth 2.0 Client ID (Web)
    # Callback URL: http://localhost:8000/api/v1/email/auth/callback
    # Scopes: gmail.send + userinfo.email
    google_client_id: str = ""
    google_client_secret: str = ""

    # Gmail SMTP App Password (fallback — used when no OAuth token)
    gmail_sender: str = ""          # e.g. yourname@gmail.com
    gmail_app_password: str = ""    # Google Account → Security → App passwords

    # JIRA — OAuth 2.0 (preferred, user-level access)
    # Setup: https://developer.atlassian.com/console/myapps/ → OAuth 2.0 app
    # Callback URL: http://localhost:8000/api/v1/jira/auth/callback
    # Scopes: read:jira-work  write:jira-work  offline_access
    atlassian_client_id: str = ""
    atlassian_client_secret: str = ""

    # JIRA — API key fallback (service account, used when no OAuth token)
    jira_base_url: str = ""         # e.g. https://your-org.atlassian.net
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "TSA"
    jira_epic_type: str = "Epic"
    jira_story_type: str = "Story"
    jira_subtask_type: str = "Subtask"

    # Slack JIRA Helper
    slack_signing_secret: str = ""
    slack_bot_token: str = ""
    slack_jira_approver_ids: str = ""
    slack_jira_default_project_key: str = ""

    @property
    def pg_conn_string(self) -> str:
        """Synchronous psycopg connection string for LangGraph checkpointer."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        ).replace(
            "sqlite+aiosqlite://", ""  # not valid for pg checkpointer
        )


settings = Settings()
