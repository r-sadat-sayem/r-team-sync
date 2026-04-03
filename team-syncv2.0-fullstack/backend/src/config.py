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

    # Database — LangGraph checkpointer + app tables share one DB
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # Auth
    backend_api_key: str = "dev-change-me"

    # Rakuten AI Gateway — Anthropic (Claude)
    rakuten_ai_gateway_key: str = ""
    rakuten_anthropic_base_url: str = "https://api.ai.public.rakuten-it.com/anthropic/"
    rakuten_anthropic_model: str = "claude-3-7-sonnet-20250219"

    # Gmail SMTP (App Password)
    gmail_sender: str = ""          # e.g. yourname@gmail.com
    gmail_app_password: str = ""    # Google Account → Security → App passwords

    # JIRA
    jira_base_url: str = ""         # e.g. https://your-org.atlassian.net
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "TSA"
    jira_epic_type: str = "Epic"
    jira_story_type: str = "Story"
    jira_subtask_type: str = "Subtask"

    @property
    def pg_conn_string(self) -> str:
        """Synchronous psycopg connection string for LangGraph checkpointer."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        ).replace(
            "sqlite+aiosqlite://", ""  # not valid for pg checkpointer
        )


settings = Settings()
