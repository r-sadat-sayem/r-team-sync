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
from src.db import init_db
from src.routers import ai, auth, chat, email_auth, jira_auth, sessions, slack_helper

_log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
# When DEBUG=true, force all loggers (including third-party) to DEBUG
if settings.debug:
    logging.getLogger().setLevel(logging.DEBUG)
    for _name in ("src", "langgraph", "langchain", "httpx", "uvicorn", "fastapi"):
        logging.getLogger(_name).setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: compile the LangGraph workflow with a PostgreSQL checkpointer.
    The graph is stored on app.state so every request handler can access it.
    """
    from src.graph.graph import build_graph

    await init_db()

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
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(ai.router)
app.include_router(jira_auth.router)
app.include_router(email_auth.router)
app.include_router(slack_helper.router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
