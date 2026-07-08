"""
guardrails.py — Security layer for Unity26.

Provides:
  1. Input sanitisation — blocks prompt-injection patterns before any text
     reaches the Gemini API.
  2. Output validation — cross-checks LLM-generated responses against the
     safety-agent-approved facts.
  3. Rate-limiting stub — simple in-memory per-session counter.
"""

from __future__ import annotations

import re
import time
from typing import Any


# ---------------------------------------------------------------------------
# 1. PROMPT-INJECTION DETECTION
# ---------------------------------------------------------------------------

# Patterns commonly used in prompt-injection attacks.
# Each tuple: (compiled regex, human-readable label).
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "instruction_override"),
    (re.compile(r"ignore\s+(all\s+)?above", re.I), "instruction_override"),
    (re.compile(r"disregard\s+(all\s+)?prior", re.I), "instruction_override"),
    (re.compile(r"system\s*:", re.I), "role_hijack"),
    (re.compile(r"you\s+are\s+now\s+", re.I), "role_hijack"),
    (re.compile(r"act\s+as\s+(if\s+you\s+are\s+)?a?\s*(different|new)\s+(ai|assistant|bot)", re.I), "role_hijack"),
    (re.compile(r"reveal\s+(your|the)\s+(system|hidden|secret)\s+prompt", re.I), "data_exfil"),
    (re.compile(r"print\s+(your|the)\s+(system|initial)\s+(prompt|instructions)", re.I), "data_exfil"),
    (re.compile(r"<\s*/?\s*script", re.I), "xss_attempt"),
    (re.compile(r"\{\{.*\}\}", re.I), "template_injection"),
]

# Reject inputs with an excessive ratio of special characters (possible
# obfuscation or binary payload).
_MAX_SPECIAL_CHAR_RATIO = 0.4
_SPECIAL_CHARS = re.compile(r"[^a-zA-Z0-9\s.,!?'\"-]")


def sanitise_input(text: str) -> tuple[str, bool, str | None]:
    """
    Sanitise user-facing text before it reaches the LLM.

    Returns:
        (cleaned_text, is_safe, rejection_reason)
        If ``is_safe`` is False, the query should NOT be forwarded to Gemini.
    """
    if not text or not text.strip():
        return ("", False, "empty_input")

    stripped = text.strip()

    # Check for injection patterns
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(stripped):
            return ("", False, f"prompt_injection_detected:{label}")

    # Check special-character ratio
    special_count = len(_SPECIAL_CHARS.findall(stripped))
    total = len(stripped)
    if total > 0 and (special_count / total) > _MAX_SPECIAL_CHAR_RATIO:
        return ("", False, "excessive_special_characters")

    # Length guard — reject extremely long inputs (> 2000 chars)
    if len(stripped) > 2000:
        return (stripped[:2000], True, "input_truncated")

    return (stripped, True, None)


# ---------------------------------------------------------------------------
# 2. OUTPUT VALIDATION
# ---------------------------------------------------------------------------

def validate_output(
    llm_response: str,
    approved_gates: list[dict],
    approved_amenities: list[dict] | None = None,
) -> tuple[str, bool]:
    """
    Cross-check the LLM's response against safety-agent-approved facts.

    If the response mentions a gate that was NOT in the approved list,
    we return a safe templated fallback instead.

    Returns:
        (final_response, was_overridden)
    """
    if not approved_gates and not approved_amenities:
        # Nothing to cross-check — allow through.
        return (llm_response, False)

    # Build set of approved gate IDs and names (case-insensitive)
    approved_ids: set[str] = set()
    approved_names: set[str] = set()
    for g in approved_gates:
        approved_ids.add(g.get("id", "").upper())
        approved_names.add(g.get("name", "").lower())

    # Scan response for gate references that are NOT in the approved set.
    # We look for patterns like "Gate X" where X is an ID we recognise.
    gate_mentions = re.findall(r"Gate\s+([A-Ha-h])\b", llm_response)
    for mention in gate_mentions:
        gate_id = f"G{mention.upper()}" if not mention.upper().startswith("G") else mention.upper()
        # Map single letter to gate ID format (Gate A -> G1, etc.)
        letter_to_id = {
            "A": "G1", "B": "G2", "C": "G3", "D": "G4",
            "E": "G5", "F": "G6", "G": "G7", "H": "G8",
        }
        mapped_id = letter_to_id.get(mention.upper(), mention.upper())
        if mapped_id not in approved_ids:
            # Mismatch detected — fall back to safe template
            best_gate = approved_gates[0] if approved_gates else None
            if best_gate:
                fallback = (
                    f"Based on current conditions, I recommend heading to "
                    f"{best_gate['name']} (crowd density: {best_gate.get('crowd_density', '?')}%). "
                    f"Please follow steward directions for the safest route."
                )
            else:
                fallback = (
                    "I'm unable to confirm a specific route right now. "
                    "Please follow steward directions or head to the nearest open gate."
                )
            return (fallback, True)

    return (llm_response, False)


# ---------------------------------------------------------------------------
# 3. RATE LIMITING (in-memory stub)
# ---------------------------------------------------------------------------

# session_id → list of timestamps
_rate_store: dict[str, list[float]] = {}
_MAX_REQUESTS_PER_MINUTE = 15


def check_rate_limit(session_id: str) -> bool:
    """
    Return True if the session is within the rate limit, False if exceeded.
    Uses a sliding-window of 60 seconds.
    """
    now = time.time()
    window = now - 60.0

    if session_id not in _rate_store:
        _rate_store[session_id] = []

    # Prune old entries
    _rate_store[session_id] = [ts for ts in _rate_store[session_id] if ts > window]

    if len(_rate_store[session_id]) >= _MAX_REQUESTS_PER_MINUTE:
        return False

    _rate_store[session_id].append(now)
    return True


def reset_rate_limit(session_id: str) -> None:
    """Clear rate-limit history for a session (useful for testing)."""
    _rate_store.pop(session_id, None)
