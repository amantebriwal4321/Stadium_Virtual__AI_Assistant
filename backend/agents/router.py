"""
router.py — Router Agent (Gemini API call #1).

Classifies the user's intent into one of a fixed set of categories and
extracts key entities.  Uses Gemini ``gemini-2.0-flash`` in JSON mode for
fast, structured output.
"""

from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai

# Valid intent labels — the router MUST choose one of these.
VALID_INTENTS = [
    "navigation",
    "safety_check",
    "amenity_search",
    "transport",
    "policy_question",
    "emergency",
    "general_chat",
]

_SYSTEM_PROMPT = """\
You are the ROUTER for Setu, an AI stadium assistant for FIFA World Cup 2026.

Your ONLY job is to classify the user's intent and extract relevant entities.
Respond with valid JSON matching this schema — NO extra text, NO markdown fences:

{
  "intent": "<one of: navigation, safety_check, amenity_search, transport, policy_question, emergency, general_chat>",
  "entities": {
    "destination": "<string or null — e.g. 'Gate A', 'restroom', 'medical tent'>",
    "amenity_type": "<string or null — e.g. 'restroom', 'food', 'medical', 'prayer_room', 'lost_and_found'>",
    "urgency": "<string: 'low', 'medium', 'high', 'critical'>",
    "location_mentioned": "<string or null>"
  },
  "summary": "<one-sentence summary of what the user needs>"
}

Rules:
- If the user mentions an emergency, medical crisis, fire, stampede, or
  security threat, set intent = "emergency" and urgency = "critical".
- If the user asks about stadium rules, bag policy, re-entry, prohibited
  items, etc., set intent = "policy_question".
- If the user asks where something is (gate, exit, entrance), use "navigation".
- If the user asks about nearby restrooms, food, prayer rooms, medical tents,
  use "amenity_search" and populate amenity_type.
- If the user asks about parking, shuttle, metro, transport to/from stadium,
  use "transport".
- If the user asks about crowd levels or gate safety, use "safety_check".
- For greetings, chit-chat, or anything else, use "general_chat".
"""


def _get_model() -> genai.GenerativeModel:
    """Lazily initialise the Gemini model."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,  # low temp for deterministic classification
        ),
    )


async def classify(query: str, fan_profile: dict) -> dict:
    """
    Send the user query + fan context to Gemini and return structured
    router output.  Falls back to ``general_chat`` on any failure.
    """
    model = _get_model()

    user_message = (
        f"Fan profile: {json.dumps(fan_profile)}\n"
        f"User query: {query}"
    )

    try:
        response = model.generate_content(
            [
                {"role": "user", "parts": [{"text": _SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": "Understood. I will classify the query and respond with valid JSON only."}]},
                {"role": "user", "parts": [{"text": user_message}]},
            ]
        )
        result = json.loads(response.text)

        # Validate intent
        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = "general_chat"

        return result

    except Exception as exc:
        # Graceful degradation — use keyword-based classification
        return _keyword_fallback_classify(query, fan_profile, exc)


def _keyword_fallback_classify(query: str, fan_profile: dict, exc: Exception) -> dict:
    """
    Rule-based intent classifier used when Gemini API is unavailable.
    Matches keywords/phrases to intents so the pipeline can still route
    queries correctly without AI.
    """
    q = query.lower().strip()

    # --- Emergency keywords (highest priority) ---
    emergency_kw = ["emergency", "fire", "stampede", "attack", "bomb", "shooting",
                     "medical emergency", "help me", "someone collapsed", "security threat"]
    if any(kw in q for kw in emergency_kw):
        return {
            "intent": "emergency",
            "entities": {"destination": None, "amenity_type": None, "urgency": "critical", "location_mentioned": None},
            "summary": f"Emergency detected via keyword match",
            "_fallback": True,
        }

    # --- Policy keywords ---
    policy_kw = ["bag", "policy", "rule", "prohibited", "banned", "allowed", "bring",
                 "re-entry", "reentry", "entry", "ticket", "size", "backpack",
                 "camera", "food allowed", "drink", "bottle", "umbrella", "flag",
                 "banner", "smoke", "smoking", "alcohol", "pet", "animal"]
    if any(kw in q for kw in policy_kw):
        return {
            "intent": "policy_question",
            "entities": {"destination": None, "amenity_type": None, "urgency": "low", "location_mentioned": None},
            "summary": f"Policy question detected via keyword match: {q[:60]}",
            "_fallback": True,
        }

    # --- Amenity keywords ---
    amenity_map = {
        "restroom": ["restroom", "bathroom", "toilet", "washroom", "loo", "wc"],
        "food": ["food", "eat", "restaurant", "snack", "hungry", "halal", "vegetarian",
                 "vegan", "kosher", "cafe", "cafeteria", "concession"],
        "medical": ["medical", "first aid", "nurse", "doctor", "injured", "hurt",
                     "feeling sick", "dizzy", "faint", "medicine", "pharmacy"],
        "prayer_room": ["prayer", "pray", "mosque", "chapel", "worship", "meditation"],
        "lost_and_found": ["lost", "found", "missing", "dropped", "left behind"],
    }
    for amenity_type, keywords in amenity_map.items():
        if any(kw in q for kw in keywords):
            return {
                "intent": "amenity_search",
                "entities": {"destination": None, "amenity_type": amenity_type, "urgency": "low", "location_mentioned": None},
                "summary": f"Amenity search ({amenity_type}) detected via keyword match",
                "_fallback": True,
            }

    # --- Navigation keywords ---
    nav_kw = ["where", "how to get", "directions", "nearest gate", "find gate",
              "gate a", "gate b", "gate c", "gate d", "gate e", "gate f", "gate g", "gate h",
              "entrance", "exit", "way to", "path to", "locate", "which gate", "go to",
              "seat", "section", "stand", "tier", "level", "block"]
    if any(kw in q for kw in nav_kw):
        destination = None
        for g in ["gate a", "gate b", "gate c", "gate d", "gate e", "gate f", "gate g", "gate h"]:
            if g in q:
                destination = g.title()
                break
        return {
            "intent": "navigation",
            "entities": {"destination": destination, "amenity_type": None, "urgency": "low", "location_mentioned": destination},
            "summary": f"Navigation request detected via keyword match",
            "_fallback": True,
        }

    # --- Safety / crowd keywords ---
    safety_kw = ["crowd", "crowded", "density", "busy", "packed", "safe", "safety",
                 "least crowded", "emptiest", "quietest", "safest", "capacity",
                 "how full", "how many people", "congestion"]
    if any(kw in q for kw in safety_kw):
        return {
            "intent": "safety_check",
            "entities": {"destination": None, "amenity_type": None, "urgency": "medium", "location_mentioned": None},
            "summary": f"Safety/crowd check detected via keyword match",
            "_fallback": True,
        }

    # --- Transport keywords ---
    transport_kw = ["transport", "parking", "park", "shuttle", "bus", "metro", "subway",
                    "train", "taxi", "uber", "ride", "how to leave", "how to reach",
                    "getting here", "getting home", "drive"]
    if any(kw in q for kw in transport_kw):
        return {
            "intent": "transport",
            "entities": {"destination": None, "amenity_type": None, "urgency": "low", "location_mentioned": None},
            "summary": f"Transport query detected via keyword match",
            "_fallback": True,
        }

    # --- Default: general chat ---
    return {
        "intent": "general_chat",
        "entities": {"destination": None, "amenity_type": None, "urgency": "low", "location_mentioned": None},
        "summary": f"General chat (keyword fallback, Gemini unavailable: {type(exc).__name__})",
        "_fallback": True,
        "_error": str(exc),
    }

