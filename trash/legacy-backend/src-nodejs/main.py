"""
TeamSync AI — FastAPI application entry point
=============================================
Start:  uvicorn src.main:app --reload --port 8000
Docs:   http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routers import ai

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown hooks) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("TeamSync AI backend starting (provider=%s)", settings.ai_provider)
    yield
    logger.info("TeamSync AI backend shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TeamSync AI Backend",
    description=(
        "Python backend for the TeamSync AI PRD automation system. "
        "Provides REST API endpoints for chat proxying, PRD storage, JIRA integration, "
        "and Rakuten AI Gateway access."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev
        "http://localhost:4040",   # Demo page
        "http://localhost:5678",   # n8n (for health checks)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ai.router)

# Additional routers (add as implemented):
# from src.routers import chat, prd, sessions, jira, health
# app.include_router(chat.router)
# app.include_router(prd.router)
# app.include_router(sessions.router)
# app.include_router(jira.router)
# app.include_router(health.router)


# ── Built-in health endpoints ─────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Liveness probe")
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/status", tags=["Health"], summary="Readiness probe")
async def status_check() -> dict:
    """Check that all dependencies are reachable."""
    components: dict[str, str] = {}

    # Check AI provider
    try:
        ai_health = await ai.ai_service.health_check()
        components.update(ai_health)
    except Exception as exc:
        components["ai"] = f"error: {exc}"

    overall = "ready" if all("error" not in v for v in components.values()) else "degraded"
    return {
        "status": overall,
        "provider": settings.ai_provider,
        "components": components,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
