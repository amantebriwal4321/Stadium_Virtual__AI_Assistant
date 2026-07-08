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
        # Graceful degradation — never crash the pipeline.
        return {
            "intent": "general_chat",
            "entities": {"destination": None, "amenity_type": None, "urgency": "low", "location_mentioned": None},
            "summary": f"Router fallback due to error: {type(exc).__name__}",
            "_error": str(exc),
        }
