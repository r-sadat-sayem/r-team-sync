"""Pydantic request/response schemas for the AI endpoint."""
from typing import Literal
from pydantic import BaseModel, Field


class AIQueryRequest(BaseModel):
    """POST /api/v1/ai/query"""

    prompt: str = Field(..., min_length=1, max_length=32_000, description="User message")
    system: str | None = Field(
        default=None,
        max_length=8000,
        description="Optional system prompt to inject before the conversation",
    )
    provider: Literal["rakuten_claude", "rakuten_openai", "rakuten_llm", "ollama"] | None = Field(
        default=None,
        description="Override the default AI_PROVIDER for this request",
    )
    model: str | None = Field(
        default=None,
        description="Override the default model for this request",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=16384,
        description="Maximum tokens in the response",
    )
    web_search: bool = Field(
        default=False,
        description="Enable real-time web search (Claude only). Costs additional tokens.",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "prompt": "What are the latest AI frameworks released in Q1 2025?",
            "web_search": True,
            "provider": "rakuten_claude",
        }
    }}


class AIUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AIQueryResponse(BaseModel):
    """Response from POST /api/v1/ai/query"""

    content: str = Field(..., description="The AI-generated response text")
    provider: str = Field(..., description="Provider used: rakuten_claude | rakuten_openai | ...")
    model: str = Field(..., description="Model identifier used for this response")
    usage: AIUsage = Field(default_factory=AIUsage)

    model_config = {"json_schema_extra": {
        "example": {
            "content": "The latest AI frameworks released in Q1 2025 include...",
            "provider": "rakuten_claude",
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 48, "output_tokens": 312, "total_tokens": 360},
        }
    }}
