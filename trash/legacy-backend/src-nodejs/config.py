"""Application configuration — reads from environment variables via pydantic-settings."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ─────────────────────────────────────────────────────────────
    debug: bool = False
    log_level: str = "info"

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./teamsync_dev.db",
        description="Async SQLAlchemy connection URL",
    )

    # ── Auth ───────────────────────────────────────────────────────────────
    backend_api_key: str = Field(
        default="dev-key",
        description="Shared API key required in X-API-Key header",
    )

    # ── n8n integration ────────────────────────────────────────────────────
    n8n_base_url: str = Field(
        default="http://localhost:5678",
        description="Internal URL of the n8n instance",
    )
    n8n_chat_webhook_id: str = Field(
        default="unified-webhook-id",
        description="Webhook ID of the Chat Trigger node in n8n",
    )

    @property
    def n8n_chat_webhook_url(self) -> str:
        return f"{self.n8n_base_url}/webhook/{self.n8n_chat_webhook_id}/chat"

    # ── AI provider selection ──────────────────────────────────────────────
    # One of: "rakuten_claude" | "rakuten_openai" | "rakuten_llm" | "ollama"
    ai_provider: str = Field(default="rakuten_claude")

    # ── Rakuten AI Gateway ─────────────────────────────────────────────────
    rakuten_ai_gateway_key: str = Field(
        default="",
        description="Rakuten AI Gateway API key (raik-...)",
    )
    # Anthropic (Claude) via Rakuten
    rakuten_anthropic_base_url: str = "https://api.ai.public.rakuten-it.com/anthropic/"
    rakuten_anthropic_model: str = "claude-sonnet-4-20250514"
    # OpenAI via Rakuten
    rakuten_openai_base_url: str = "https://api.ai.public.rakuten-it.com/openai/v1"
    rakuten_openai_model: str = "gpt-4.1"
    # Rakuten native LLMs (OpenAI-compatible)
    rakuten_llm_base_url: str = "https://api.ai.public.rakuten-it.com/rakutenllms/v1/"
    rakuten_llm_model: str = "rakutenai-3.0"

    # ── Ollama (local dev fallback) ────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:latest"


# Module-level singleton — import and use: from src.config import settings
settings = Settings()
