"""
TeamSync v2.0 — FastAPI application entry point

Start:  uvicorn src.main:app --reload --port 8000
Docs:   http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routers import ai, chat, sessions

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: compile the LangGraph workflow with a PostgreSQL checkpointer.
    The graph is stored on app.state so every request handler can access it.
    """
    from src.graph.graph import build_graph

    if "postgresql" in settings.database_url:
        # Production / Docker — use PostgreSQL checkpointer
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            settings.pg_conn_string
        ) as checkpointer:
            await checkpointer.setup()
            app.state.graph = build_graph(checkpointer=checkpointer)
            logger.info("LangGraph using PostgreSQL checkpointer")
            yield
    else:
        # Local dev without Postgres — in-memory checkpointer (state lost on restart)
        from langgraph.checkpoint.memory import MemorySaver

        app.state.graph = build_graph(checkpointer=MemorySaver())
        logger.warning(
            "LangGraph using in-memory checkpointer — conversations reset on restart. "
            "Set DATABASE_URL to a PostgreSQL URL for persistent sessions."
        )
        yield


app = FastAPI(
    title="TeamSync v2.0",
    description="LangGraph + Anthropic SDK PRD automation backend.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(ai.router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
