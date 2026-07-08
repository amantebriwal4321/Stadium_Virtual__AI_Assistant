"""
responder.py — Response Agent (Gemini API call #2).

Takes the structured decision JSON from the orchestrator and produces a warm,
natural, multilingual response for the fan.  Uses streaming for real-time
token delivery.

CRITICAL GROUNDING RULE (encoded in system prompt):
  "You must only state facts present in the provided JSON context.
   Do not invent gate numbers, distances, or policies.
   If information is missing, say so honestly."
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator

import google.generativeai as genai

# Mapping of ISO language codes to display names for the system prompt.
_LANG_MAP = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "ar": "Arabic",
}


def _build_system_prompt(language_code: str) -> str:
    lang = _LANG_MAP.get(language_code, "English")
    return f"""\
You are Setu (सेतु), a friendly AI stadium companion for FIFA World Cup 2026.
You are responding to a fan who speaks {lang}.  Respond ONLY in {lang}.

STRICT GROUNDING RULES — VIOLATION IS UNACCEPTABLE:
1. You must ONLY state facts present in the provided JSON context below.
2. Do NOT invent gate numbers, distances, crowd percentages, or policies
   that are not explicitly in the context.
3. If information is missing from the context, say "I don't have that
   information right now — please ask a steward for help."
4. Keep responses concise, warm, and actionable.  Use emoji sparingly
   for friendliness (1-2 per message max).
5. If the context includes an emergency protocol message, relay it
   IMMEDIATELY and VERBATIM — do not soften or delay it.
6. When recommending a gate, always mention its name, current crowd
   density, and accessibility status exactly as provided.
7. For policy questions, quote the policy text provided — do not
   paraphrase in a way that changes the meaning.
"""


def _get_model() -> genai.GenerativeModel:
    """Lazily initialise the Gemini model for response generation."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
        ),
    )


async def generate_response(context: dict, language: str = "en") -> str:
    """
    Generate a non-streaming response (used for trace logging / testing).
    """
    model = _get_model()
    system = _build_system_prompt(language)
    user_msg = f"Context for your response:\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```"

    try:
        response = model.generate_content(
            [
                {"role": "user", "parts": [{"text": system}]},
                {"role": "model", "parts": [{"text": f"Understood. I will respond in {_LANG_MAP.get(language, 'English')} using only the facts from the provided context."}]},
                {"role": "user", "parts": [{"text": user_msg}]},
            ]
        )
        return response.text
    except Exception as exc:
        return f"I'm sorry, I encountered an issue generating a response. Please ask a steward for help. (Error: {type(exc).__name__})"


async def generate_response_stream(context: dict, language: str = "en") -> AsyncGenerator[str, None]:
    """
    Stream the response token-by-token via Gemini's streaming API.
    Yields text chunks as they arrive.
    """
    model = _get_model()
    system = _build_system_prompt(language)
    user_msg = f"Context for your response:\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```"

    try:
        response = model.generate_content(
            [
                {"role": "user", "parts": [{"text": system}]},
                {"role": "model", "parts": [{"text": f"Understood. I will respond in {_LANG_MAP.get(language, 'English')} using only the facts from the provided context."}]},
                {"role": "user", "parts": [{"text": user_msg}]},
            ],
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        yield f"I'm sorry, I encountered an issue. Please ask a steward for assistance. (Error: {type(exc).__name__})"
