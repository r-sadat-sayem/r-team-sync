from __future__ import annotations

"""POST /api/v1/ai/query — direct access to the Rakuten AI Gateway."""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config import settings
from src.middleware.auth import require_current_user

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])
logger = logging.getLogger(__name__)


class AIRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: Optional[str] = None
    provider: Optional[Literal["rakuten_claude", "rakuten_openai", "rakuten_llm"]] = None
    model: Optional[str] = None
    max_tokens: int = Field(default=2048, ge=1, le=16384)
    web_search: bool = False


class AIResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@router.post("/query", response_model=AIResponse, dependencies=[Depends(require_current_user)])
async def query(body: AIRequest) -> AIResponse:
    from anthropic import AsyncAnthropic

    provider = body.provider or "rakuten_claude"
    model = body.model or settings.rakuten_anthropic_model

    if provider == "rakuten_claude":
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_model = ChatAnthropic(
            model_name=model,
            temperature=0.7,
            max_tokens=body.max_tokens,
            anthropic_api_url=settings.rakuten_anthropic_base_url,
            anthropic_api_key="test",
            default_headers={"Authorization": f"Bearer {settings.rakuten_ai_gateway_key}"},
        )

        msgs = []
        if body.system:
            msgs.append(SystemMessage(content=body.system))
        msgs.append(HumanMessage(content=body.prompt))

        try:
            resp = await lc_model.ainvoke(msgs)
        except Exception as exc:
            logger.error("Rakuten Claude error: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        usage   = resp.usage_metadata or {}
        return AIResponse(
            content=content,
            provider="rakuten_claude",
            model=model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Provider {provider!r} not yet implemented. Use rakuten_claude.",
    )


@router.get("/providers", dependencies=[Depends(require_current_user)])
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
