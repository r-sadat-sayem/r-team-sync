"""
AI Service — Rakuten AI Gateway integration
============================================
Supports all three Rakuten gateway providers via their respective SDKs:

  Provider              SDK              Auth style
  ─────────────────────────────────────────────────────────────────
  Claude (Anthropic)    Anthropic SDK    auth_token header (NOT api_key)
  OpenAI models         OpenAI SDK       api_key / Bearer token
  Rakuten native LLMs   OpenAI SDK       api_key / Bearer token

SDK chosen over raw REST because:
  - Automatic retry on transient errors
  - Streaming helpers built in
  - Type-safe request/response objects
  - Better error messages

Usage:
    from src.services.ai_service import AIService, ai_service
    result = await ai_service.query("Tell me about Rakuten", web_search=True)
"""

import asyncio
import logging
from typing import Any

import anthropic
import openai

from src.config import settings

logger = logging.getLogger(__name__)


class RakutenClaudeClient:
    """
    Anthropic SDK pointed at the Rakuten AI Gateway.

    Critical: uses `auth_token`, NOT `api_key`.
    Passing the Rakuten key as api_key will return 401.
    """

    def __init__(self) -> None:
        self._sync_client = anthropic.Anthropic(
            base_url=settings.rakuten_anthropic_base_url,
            auth_token=settings.rakuten_ai_gateway_key,
        )
        self._async_client = anthropic.AsyncAnthropic(
            base_url=settings.rakuten_anthropic_base_url,
            auth_token=settings.rakuten_ai_gateway_key,
        )

    async def create(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 8192,
        system: str | None = None,
        web_search: bool = False,
        max_web_searches: int = 3,
    ) -> anthropic.types.Message:
        """
        Send a message to Claude via Rakuten.
        Pass web_search=True to enable real-time web search.
        """
        resolved_model = model or settings.rakuten_anthropic_model

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if web_search:
            kwargs["tools"] = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_web_searches,
                }
            ]

        logger.debug(
            "rakuten_claude.create model=%s web_search=%s messages=%d",
            resolved_model,
            web_search,
            len(messages),
        )
        return await self._async_client.messages.create(**kwargs)

    def create_sync(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 8192,
        system: str | None = None,
        web_search: bool = False,
        max_web_searches: int = 3,
    ) -> anthropic.types.Message:
        """Synchronous version for use outside async context."""
        resolved_model = model or settings.rakuten_anthropic_model
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if web_search:
            kwargs["tools"] = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_web_searches,
                }
            ]
        return self._sync_client.messages.create(**kwargs)


class RakutenOpenAIClient:
    """
    OpenAI SDK pointed at the Rakuten AI Gateway.
    Works for both OpenAI models and Rakuten native LLMs.
    Uses standard api_key / Bearer token auth.
    """

    def __init__(self, base_url: str) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=settings.rakuten_ai_gateway_key,
            base_url=base_url,
        )

    async def chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str:
        """
        Chat completion via Rakuten OpenAI-compatible endpoint.
        Returns the assistant message content as a string.
        """
        logger.debug(
            "rakuten_openai.chat model=%s messages=%d stream=%s",
            model,
            len(messages),
            stream,
        )
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )
        if stream:
            raise NotImplementedError("Use stream_chat() for streaming responses")
        return response.choices[0].message.content or ""

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 4096,
    ):
        """Async generator that yields content chunks for streaming responses."""
        async with await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta


class AIService:
    """
    Unified AI interface for the TeamSync backend.

    Provider routing (set AI_PROVIDER env var):
      rakuten_claude  — Claude Sonnet 4 via Rakuten (best quality, web search)
      rakuten_openai  — OpenAI models via Rakuten (GPT-4.1 etc.)
      rakuten_llm     — Rakuten native LLMs (cost-effective)
      ollama          — Local Ollama (dev/offline only)
    """

    def __init__(self) -> None:
        self._claude = RakutenClaudeClient()
        self._openai_rakuten = RakutenOpenAIClient(settings.rakuten_openai_base_url)
        self._rakuten_llm = RakutenOpenAIClient(settings.rakuten_llm_base_url)

    async def query(
        self,
        prompt: str,
        system: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        web_search: bool = False,
    ) -> "AIResponse":
        """
        Route a query to the configured AI provider.

        Args:
            prompt:     User message content.
            system:     Optional system prompt.
            provider:   Override AI_PROVIDER for this call.
            model:      Override default model for this call.
            max_tokens: Maximum response tokens.
            web_search: Enable real-time web search (Claude only).

        Returns:
            AIResponse with content, provider, model, and usage info.
        """
        resolved_provider = provider or settings.ai_provider
        messages = [{"role": "user", "content": prompt}]

        try:
            if resolved_provider == "rakuten_claude":
                return await self._query_claude(
                    messages, system=system, model=model,
                    max_tokens=max_tokens, web_search=web_search,
                )
            elif resolved_provider == "rakuten_openai":
                return await self._query_openai(
                    messages, model=model or settings.rakuten_openai_model,
                    max_tokens=max_tokens,
                )
            elif resolved_provider == "rakuten_llm":
                return await self._query_rakuten_llm(
                    messages, model=model or settings.rakuten_llm_model,
                    max_tokens=max_tokens,
                )
            elif resolved_provider == "ollama":
                return await self._query_ollama(
                    messages, system=system, model=model,
                    max_tokens=max_tokens,
                )
            else:
                raise ValueError(f"Unknown AI provider: {resolved_provider!r}")

        except Exception as exc:
            logger.error("ai_service.query failed provider=%s: %s", resolved_provider, exc)
            raise

    async def query_for_prd(
        self,
        context_summary: str,
        system: str | None = None,
    ) -> "AIResponse":
        """
        Convenience method for PRD generation — always uses Claude with max tokens.
        This produces the highest-quality PRD output.
        """
        return await self.query(
            prompt=f"Generate a comprehensive PRD based on:\n\n{context_summary}",
            system=system,
            provider="rakuten_claude",
            model=settings.rakuten_anthropic_model,
            max_tokens=8192,
            web_search=False,
        )

    # ── Private provider implementations ────────────────────────────────────

    async def _query_claude(
        self,
        messages: list[dict],
        system: str | None,
        model: str | None,
        max_tokens: int,
        web_search: bool,
    ) -> "AIResponse":
        response = await self._claude.create(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            system=system,
            web_search=web_search,
        )

        # Extract text from Claude's content blocks
        # Response may contain text blocks and tool_result blocks (web search)
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return AIResponse(
            content="\n".join(text_parts),
            provider="rakuten_claude",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def _query_openai(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
    ) -> "AIResponse":
        content = await self._openai_rakuten.chat(
            messages=messages, model=model, max_tokens=max_tokens
        )
        return AIResponse(content=content, provider="rakuten_openai", model=model)

    async def _query_rakuten_llm(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
    ) -> "AIResponse":
        content = await self._rakuten_llm.chat(
            messages=messages, model=model, max_tokens=max_tokens
        )
        return AIResponse(content=content, provider="rakuten_llm", model=model)

    async def _query_ollama(
        self,
        messages: list[dict],
        system: str | None,
        model: str | None,
        max_tokens: int,
    ) -> "AIResponse":
        """Fallback to local Ollama via OpenAI-compatible endpoint."""
        ollama_client = RakutenOpenAIClient(base_url=f"{settings.ollama_base_url}/v1")
        resolved_model = model or settings.ollama_model
        if system:
            messages = [{"role": "system", "content": system}] + messages
        content = await ollama_client.chat(
            messages=messages, model=resolved_model, max_tokens=max_tokens
        )
        return AIResponse(content=content, provider="ollama", model=resolved_model)

    async def health_check(self) -> dict[str, str]:
        """Ping each configured provider. Returns status per provider."""
        results: dict[str, str] = {}
        if settings.ai_provider.startswith("rakuten") and settings.rakuten_ai_gateway_key:
            try:
                await self._claude.create(
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=5,
                )
                results["rakuten_claude"] = "ok"
            except Exception as exc:
                results["rakuten_claude"] = f"error: {exc}"
        return results


class AIResponse:
    """Structured response from any AI provider."""

    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        self.content = content
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
            },
        }


# ── Module-level singleton ────────────────────────────────────────────────────
# Import and use directly: from src.services.ai_service import ai_service
ai_service = AIService()
