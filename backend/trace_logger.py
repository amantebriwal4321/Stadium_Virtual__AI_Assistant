"""
trace_logger.py — Observability for Setu.

Every query appends a JSON line to ``trace_log.jsonl`` recording the full
pipeline trace: timestamp, fan profile, router output, safety-agent decision,
final response text, and latency.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Write logs to the App Data Directory to avoid triggering live-server reloads
_LOG_DIR = Path("C:/Users/Lenovo/.gemini/antigravity-ide")
_LOG_FILE = _LOG_DIR / "trace_log.jsonl"


def log_trace(
    *,
    fan_profile: dict,
    user_query: str,
    router_output: dict,
    safety_decision: dict,
    rag_context: list[str] | None = None,
    final_response: str,
    latency_ms: float,
) -> dict:
    """Append a trace record and return it."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fan_profile": fan_profile,
        "user_query": user_query,
        "router_output": router_output,
        "safety_decision": safety_decision,
        "rag_context": rag_context or [],
        "final_response": final_response[:500],  # truncate for storage
        "latency_ms": round(latency_ms, 1),
    }
    with open(_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def get_recent_traces(n: int = 20) -> list[dict]:
    """Return the last *n* trace records, newest first."""
    if not _LOG_FILE.exists():
        return []
    lines = _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-n:] if len(lines) >= n else lines
    traces = []
    for line in reversed(recent):
        try:
            traces.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return traces
