"""
FastAPI router for /api/v1/ai/*
Exposes the Rakuten AI Gateway as a REST endpoint callable from the frontend
or from n8n workflows via HTTP Request node.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas.ai import AIQueryRequest, AIQueryResponse, AIUsage
from src.services.ai_service import ai_service
from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/ai", tags=["AI Gateway"])
logger = logging.getLogger(__name__)


@router.post(
    "/query",
    response_model=AIQueryResponse,
    summary="Query the AI (Rakuten AI Gateway)",
    description=(
        "Route a prompt to the configured AI provider via Rakuten AI Gateway. "
        "Supports Claude (web search), OpenAI models, and Rakuten native LLMs. "
        "Provider and model can be overridden per request."
    ),
)
async def query_ai(
    body: AIQueryRequest,
    _: None = Depends(require_api_key),
) -> AIQueryResponse:
    try:
        result = await ai_service.query(
            prompt=body.prompt,
            system=body.system,
            provider=body.provider,
            model=body.model,
            max_tokens=body.max_tokens,
            web_search=body.web_search,
        )
        return AIQueryResponse(
            content=result.content,
            provider=result.provider,
            model=result.model,
            usage=AIUsage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("AI query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {exc}",
        )


@router.get(
    "/providers",
    summary="List available AI providers",
    dependencies=[Depends(require_api_key)],
)
async def list_providers() -> dict:
    """Return available providers and their configured models."""
    from src.config import settings
    return {
        "default_provider": settings.ai_provider,
        "providers": {
            "rakuten_claude": {
                "available": bool(settings.rakuten_ai_gateway_key),
                "default_model": settings.rakuten_anthropic_model,
                "web_search": True,
                "base_url": settings.rakuten_anthropic_base_url,
            },
            "rakuten_openai": {
                "available": bool(settings.rakuten_ai_gateway_key),
                "default_model": settings.rakuten_openai_model,
                "web_search": False,
                "base_url": settings.rakuten_openai_base_url,
            },
            "rakuten_llm": {
                "available": bool(settings.rakuten_ai_gateway_key),
                "default_model": settings.rakuten_llm_model,
                "web_search": False,
                "base_url": settings.rakuten_llm_base_url,
            },
            "ollama": {
                "available": True,
                "default_model": settings.ollama_model,
                "web_search": False,
                "base_url": settings.ollama_base_url,
            },
        },
    }


@router.get(
    "/health",
    summary="Ping configured AI provider",
    dependencies=[Depends(require_api_key)],
)
async def ai_health() -> dict:
    """Check connectivity to the active AI provider."""
    result = await ai_service.health_check()
    return {"status": result}
