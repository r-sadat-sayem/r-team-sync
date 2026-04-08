import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from langgraph.checkpoint.memory import MemorySaver

from src.graph.graph import build_graph
from src.main import app


@pytest.fixture
def graph():
    """In-memory graph for unit tests — no DB required."""
    return build_graph(checkpointer=MemorySaver())


@pytest.fixture
def thread_config():
    return {"configurable": {"thread_id": "test-session-1"}}


@pytest.fixture
async def async_client():
    """Async HTTP client wired to the FastAPI app (no server needed)."""
    app.state.graph = build_graph(checkpointer=MemorySaver())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
