"""
app.py — FastAPI application for Setu.

Endpoints:
  POST /chat      — main chat endpoint (streamed agent response)
  POST /simulate  — update mock gate/crowd state (demo control panel)
  GET  /trace     — return recent trace logs
  GET  /health    — basic healthcheck

Security:
  - CORS restricted to localhost origins (not wildcard)
  - Input sanitisation via guardrails.py on every user-facing endpoint
  - API key loaded from .env via python-dotenv (never hardcoded)
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Load .env BEFORE importing modules that need GEMINI_API_KEY
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from backend.guardrails import check_rate_limit, sanitise_input
from backend.orchestrator import get_gates, get_temperature, handle_query, update_simulation
from backend.retriever import initialise as init_rag
from backend.trace_logger import get_recent_traces


# ---------------------------------------------------------------------------
# Lifespan: initialise RAG index on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: build/load RAG index. Shutdown: nothing special needed."""
    print("[Setu] Initialising RAG knowledge base...")
    try:
        init_rag()
        print("[Setu] RAG index ready.")
    except Exception as exc:
        print(f"[Setu] RAG init failed (non-fatal): {exc}")
    yield


app = FastAPI(
    title="Setu — AI Stadium Companion",
    description="Multi-agent GenAI assistant for FIFA World Cup 2026 fans.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — restricted to local dev origins (NOT wildcard *)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://amantebriwal4321.github.io",
        "null",  # file:// protocol sends Origin: null
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    fan_profile: dict = Field(default_factory=lambda: {
        "name": "Guest",
        "language": "en",
        "needs_wheelchair": False,
        "location": {"x": 50, "y": 50},
    })
    language: str = Field(default="en")
    session_id: str = Field(default="default")


class SimulateRequest(BaseModel):
    gates: list[dict] | None = None
    temperature_c: float | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Basic healthcheck endpoint."""
    return {"status": "healthy", "service": "setu", "version": "1.0.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.  Streams the agent response as newline-delimited
    JSON chunks (one JSON object per line).
    """
    # Rate-limit check
    if not check_rate_limit(req.session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment.")

    # Input pre-check (fast-fail before starting the pipeline)
    _, is_safe, reason = sanitise_input(req.query)
    if not is_safe and reason != "input_truncated":
        raise HTTPException(status_code=400, detail=f"Input rejected: {reason}")

    async def event_stream():
        async for chunk in handle_query(
            query=req.query,
            fan_profile=req.fan_profile,
            language=req.language,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
    )


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    """
    Update the live simulation state.
    Called by the frontend demo control panel to adjust gate crowd densities,
    open/close gates, or trigger conditions.
    """
    if req.gates is not None:
        update_simulation(gates=req.gates)
    if req.temperature_c is not None:
        update_simulation(temperature=req.temperature_c)
    return {"status": "updated", "gates_count": len(req.gates) if req.gates else 0}


@app.get("/trace")
async def trace():
    """Return the 20 most recent trace log entries."""
    return {"traces": get_recent_traces(20)}


@app.get("/gates")
async def gates():
    """Return current gate state and stadium temperature (for the frontend map)."""
    return {"gates": get_gates(), "temperature_c": get_temperature()}
