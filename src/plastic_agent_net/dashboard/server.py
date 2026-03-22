"""FastAPI server with SSE for live episode streaming."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from plastic_agent_net.dashboard.routes import router

# Shared state for live episodes
_event_queue: asyncio.Queue[dict] | None = None
_current_episode: Any = None


def get_event_queue() -> asyncio.Queue[dict]:
    global _event_queue
    if _event_queue is None:
        _event_queue = asyncio.Queue()
    return _event_queue


def set_current_episode(episode: Any) -> None:
    global _current_episode
    _current_episode = episode


def get_current_episode() -> Any:
    return _current_episode


def create_app() -> FastAPI:
    app = FastAPI(title="PlasticAgentNet Dashboard", version="0.1.0")
    app.include_router(router, prefix="/api")

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return index_file.read_text()
        return "<h1>PlasticAgentNet Dashboard</h1><p>Static files not found.</p>"

    @app.get("/events")
    async def event_stream():
        queue = get_event_queue()

        async def generate():
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {"event": event.get("event", "update"), "data": json.dumps(event, default=str)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}

        return EventSourceResponse(generate())

    return app


def dashboard_event_callback(event: dict) -> None:
    """Push events to the SSE queue."""
    queue = get_event_queue()
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        pass
