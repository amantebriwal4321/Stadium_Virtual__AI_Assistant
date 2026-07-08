"""
orchestrator.py — Central orchestration loop for Setu.

Routes between the specialised agents in a single deterministic pipeline:
  1. Router Agent   (Gemini call #1 — classifies intent)
  2. Orchestrator   (this module — pure Python, NO LLM)
  3. Safety Agent   (deterministic rules engine)
  4. Response Agent  (Gemini call #2 — generates natural-language reply)

Only 2 real Gemini API calls per user query.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from backend.agents import router, safety
from backend.agents.responder import generate_response, generate_response_stream
from backend.decision_engine import (
    check_transit_recommendation,
    find_nearest_amenity,
    rank_routes,
)
from backend.guardrails import sanitise_input, validate_output
from backend.retriever import retrieve as rag_retrieve
from backend.trace_logger import log_trace

# ---------------------------------------------------------------------------
# Mock-data loader — reads current state from JSON files (or in-memory
# overrides set by the /simulate endpoint).
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent / "mock_data"

# In-memory overrides set by the simulation control panel.
# When populated, these take precedence over the JSON files.
_live_gates: list[dict] | None = None
_live_amenities: list[dict] | None = None

# Stadium temperature in °C — adjustable via the simulation control panel.
# Default simulates a warm match-day afternoon.
_live_temperature: float = 32.0


def _load_json(filename: str) -> list[dict]:
    with open(_DATA_DIR / filename, "r", encoding="utf-8") as fh:
        return json.load(fh)


def get_gates() -> list[dict]:
    """Return current gate state — live override if set, else file."""
    if _live_gates is not None:
        return _live_gates
    return _load_json("gates.json")


def get_amenities() -> list[dict]:
    """Return current amenity state."""
    if _live_amenities is not None:
        return _live_amenities
    return _load_json("amenities.json")


def get_temperature() -> float:
    """Return current stadium temperature in °C."""
    return _live_temperature


def update_simulation(
    gates: list[dict] | None = None,
    amenities: list[dict] | None = None,
    temperature: float | None = None,
) -> None:
    """Called by the /simulate endpoint to push live state changes."""
    global _live_gates, _live_amenities, _live_temperature
    if gates is not None:
        _live_gates = gates
    if amenities is not None:
        _live_amenities = amenities
    if temperature is not None:
        _live_temperature = temperature


# ---------------------------------------------------------------------------
# Main orchestration pipeline
# ---------------------------------------------------------------------------

async def handle_query(
    query: str,
    fan_profile: dict,
    language: str = "en",
) -> AsyncGenerator[str, None]:
    """
    Full orchestration pipeline.  Yields response text chunks (streaming).

    Steps:
      1. Sanitise input (guardrails)
      2. Router Agent classifies intent (Gemini call #1)
      3. Decision engine ranks routes / finds amenities
      4. Safety Agent applies rules
      5. (Optional) RAG retriever fetches policy context
      6. Response Agent generates natural reply (Gemini call #2, streaming)
      7. Output validation (guardrails)
      8. Trace logging
    """
    t_start = time.time()

    # ── Step 1: Input sanitisation ──────────────────────────────────────
    cleaned, is_safe, reason = sanitise_input(query)
    if not is_safe:
        error_msg = "I'm sorry, I couldn't process that request. Could you rephrase your question?"
        log_trace(
            fan_profile=fan_profile,
            user_query=query,
            router_output={"intent": "blocked", "reason": reason},
            safety_decision={"action": "input_blocked"},
            final_response=error_msg,
            latency_ms=(time.time() - t_start) * 1000,
        )
        yield json.dumps({
            "type": "error",
            "content": error_msg,
            "trace": {"router": {"intent": "blocked", "reason": reason}, "safety": {"action": "input_blocked"}},
        })
        return

    # ── Step 2: Router Agent (Gemini call #1) ───────────────────────────
    router_output = await router.classify(cleaned, fan_profile)
    intent = router_output.get("intent", "general_chat")
    entities = router_output.get("entities", {})
    urgency = entities.get("urgency", "low")

    # ── Step 3: Decision engine ─────────────────────────────────────────
    gates = get_gates()
    amenities = get_amenities()

    ranked_gates = rank_routes(fan_profile, gates, amenities)
    nearest_amenity = None
    transit_info = None
    rag_context: list[str] = []

    if intent == "amenity_search":
        amenity_type = entities.get("amenity_type", "restroom")
        nearest_amenity = find_nearest_amenity(
            fan_profile.get("location", {"x": 50, "y": 50}),
            amenity_type,
            amenities,
            needs_wheelchair=fan_profile.get("needs_wheelchair", False),
        )

    if intent == "transport":
        transit_info = check_transit_recommendation(
            fan_profile.get("location", {"x": 50, "y": 50}),
            distance_to_venue_km=3.5,  # mock default
        )

    # ── Step 3b: Get stadium temperature ──────────────────────────────
    temperature = get_temperature()

    # ── Step 4: Safety Agent (pure Python) ──────────────────────────────
    safety_decision = safety.evaluate(
        intent=intent,
        ranked_gates=ranked_gates,
        fan_profile=fan_profile,
        urgency=urgency,
        temperature_c=temperature,
    )

    # If emergency protocol, yield immediately and return
    if safety_decision["action"] == "emergency_protocol":
        msg = safety_decision["message"]
        log_trace(
            fan_profile=fan_profile,
            user_query=query,
            router_output=router_output,
            safety_decision=safety_decision,
            final_response=msg,
            latency_ms=(time.time() - t_start) * 1000,
        )
        yield json.dumps({
            "type": "emergency",
            "content": msg,
            "trace": {"router": router_output, "safety": safety_decision},
        })
        return

    # ── Step 5: RAG retriever (if policy question) ──────────────────────
    if intent == "policy_question":
        rag_context = rag_retrieve(cleaned, top_k=3)

    # ── Step 6: Build context for Response Agent ────────────────────────
    response_context = {
        "user_query": cleaned,
        "intent": intent,
        "fan_profile": {
            "name": fan_profile.get("name", "Fan"),
            "language": language,
            "needs_wheelchair": fan_profile.get("needs_wheelchair", False),
            "location": fan_profile.get("location", {"x": 50, "y": 50}),
        },
        "recommended_gates": [
            {
                "name": g["name"],
                "crowd_density": g["crowd_density"],
                "wheelchair_accessible": g["wheelchair_accessible"],
                "distance": g.get("distance"),
            }
            for g in safety_decision.get("approved_gates", [])[:3]
        ],
        "safety_warnings": safety_decision.get("warnings", []),
        "nearest_amenity": nearest_amenity,
        "transit_recommendation": transit_info,
        "policy_context": rag_context,
        "stadium_temperature_c": temperature,
    }

    # ── Step 7: Response Agent (Gemini call #2, streaming) ──────────────
    full_response_parts: list[str] = []

    # First yield the trace metadata
    yield json.dumps({
        "type": "trace",
        "trace": {
            "router": router_output,
            "safety": {
                "action": safety_decision["action"],
                "approved_gates": [g["name"] for g in safety_decision.get("approved_gates", [])],
                "gates_vetoed": [g["name"] for g in safety_decision.get("gates_vetoed", [])],
                "warnings": safety_decision.get("warnings", []),
                "rerouted": safety_decision.get("rerouted", False),
            },
            "rag_used": bool(rag_context),
            "rag_chunks": len(rag_context),
        },
    }) + "\n"

    async for chunk in generate_response_stream(response_context, language):
        full_response_parts.append(chunk)
        yield json.dumps({"type": "token", "content": chunk}) + "\n"

    full_response = "".join(full_response_parts)

    # ── Step 8: Output validation (guardrails) ──────────────────────────
    validated_response, was_overridden = validate_output(
        full_response,
        safety_decision.get("approved_gates", []),
    )
    if was_overridden:
        yield json.dumps({"type": "override", "content": validated_response}) + "\n"
        full_response = validated_response

    # ── Step 9: Trace logging ───────────────────────────────────────────
    latency_ms = (time.time() - t_start) * 1000
    log_trace(
        fan_profile=fan_profile,
        user_query=query,
        router_output=router_output,
        safety_decision={
            "action": safety_decision["action"],
            "approved_count": len(safety_decision.get("approved_gates", [])),
            "vetoed_count": len(safety_decision.get("gates_vetoed", [])),
            "rerouted": safety_decision.get("rerouted", False),
        },
        rag_context=rag_context,
        final_response=full_response,
        latency_ms=latency_ms,
    )

    yield json.dumps({"type": "done", "latency_ms": round(latency_ms, 1)}) + "\n"
