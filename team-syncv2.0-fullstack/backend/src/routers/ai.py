"""POST /api/v1/ai/query — direct access to the Rakuten AI Gateway."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal

from src.config import settings
from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])
logger = logging.getLogger(__name__)


class AIRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None
    provider: Literal["rakuten_claude", "rakuten_openai", "rakuten_llm"] | None = None
    model: str | None = None
    max_tokens: int = Field(default=2048, ge=1, le=16384)
    web_search: bool = False


class AIResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@router.post("/query", response_model=AIResponse, dependencies=[Depends(require_api_key)])
async def query(body: AIRequest) -> AIResponse:
    from anthropic import AsyncAnthropic

    provider = body.provider or "rakuten_claude"
    model = body.model or settings.rakuten_anthropic_model

    if provider == "rakuten_claude":
        client = AsyncAnthropic(
            base_url=settings.rakuten_anthropic_base_url,
            auth_token=settings.rakuten_ai_gateway_key,
        )
        kwargs = {
            "model": model,
            "max_tokens": body.max_tokens,
            "messages": [{"role": "user", "content": body.prompt}],
        }
        if body.system:
            kwargs["system"] = body.system
        if body.web_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

        try:
            resp = await client.messages.create(**kwargs)
        except Exception as exc:
            logger.error("Rakuten Claude error: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return AIResponse(
            content=text,
            provider="rakuten_claude",
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Provider {provider!r} not yet implemented. Use rakuten_claude.",
    )


@router.get("/providers", dependencies=[Depends(require_api_key)])
async def providers() -> dict:
    return {
        "default": "rakuten_claude",
        "available": {
            "rakuten_claude": {
                "model": settings.rakuten_anthropic_model,
                "web_search": True,
                "key_configured": bool(settings.rakuten_ai_gateway_key),
            }
        },
    }
