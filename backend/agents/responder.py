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


def _fallback_response(context: dict, language: str = "en") -> str:
    intent = context.get("intent", "general_chat")
    recommended_gates = context.get("recommended_gates", [])
    warnings = context.get("safety_warnings", [])
    nearest_amenity = context.get("nearest_amenity")
    transit_info = context.get("transit_recommendation")
    policies = context.get("policy_context", [])
    temp = context.get("stadium_temperature_c", 32)
    name = context.get("fan_profile", {}).get("name", "Fan")

    # Multilingual headers/labels
    translations = {
        "en": {
            "title": "⚽ **Setu Matchday Companion — Live Backup Mode**",
            "gates_header": "🗺️ **Recommended Gates:**",
            "warnings_header": "⚠️ **Safety Advisory:**",
            "amenity_header": "📍 **Nearest Service Location:**",
            "transit_header": "🚌 **Transit & Transport:**",
            "policies_header": "📖 **Official Stadium Guidelines:**",
            "fallback_chat": f"Hello {name}! I am Setu, your FIFA World Cup 2026 Companion. The current stadium temperature is {temp}°C.\n\nAsk me about finding the nearest restroom, least crowded gates, transport options, or stadium policies.",
            "wheelchair": "♿ Wheelchair Accessible",
            "density": "Crowd Density"
        },
        "hi": {
            "title": "⚽ **सेतु मैचडे कंपेनियन — लाइव बैकअप मोड**",
            "gates_header": "🗺️ **अनुशंसित गेट:**",
            "warnings_header": "⚠️ **सुरक्षा चेतावनी:**",
            "amenity_header": "📍 **निकटतम सेवा स्थान:**",
            "transit_header": "🚌 **पारगमन और परिवहन:**",
            "policies_header": "📖 **आधिकारिक स्टेडियम दिशानिर्देश:**",
            "fallback_chat": f"नमस्ते {name}! मैं सेतु हूँ, आपका फीफा विश्व कप 2026 साथी। वर्तमान स्टेडियम का तापमान {temp}°C है।\n\nमुझसे निकटतम शौचालय, सबसे कम भीड़ वाले गेट, परिवहन विकल्प या स्टेडियम की नीतियों के बारे में पूछें।",
            "wheelchair": "♿ व्हीलचेयर सुलभ",
            "density": "भीड़ घनत्व"
        },
        "es": {
            "title": "⚽ **Setu Companion — Modo de Respaldo en Vivo**",
            "gates_header": "🗺️ **Puertas Recomendadas:**",
            "warnings_header": "⚠️ **Aviso de Seguridad:**",
            "amenity_header": "📍 **Ubicación del Servicio más Cercano:**",
            "transit_header": "🚌 **Tránsito y Transporte:**",
            "policies_header": "📖 **Pautas Oficiales del Estadio:**",
            "fallback_chat": f"¡Hola {name}! Soy Setu, tu compañero de la Copa Mundial de la FIFA 2026. La temperatura actual del estadio es de {temp}°C.\n\nPregúntame cómo encontrar el baño más cercano, las puertas menos concurridas, las opciones de transporte o las políticas del estadio.",
            "wheelchair": "♿ Accesible para silla de ruedas",
            "density": "Densidad de la multitud"
        },
        "pt": {
            "title": "⚽ **Setu Companion — Modo de Backup ao Vivo**",
            "gates_header": "🗺️ **Portões Recomendados:**",
            "warnings_header": "⚠️ **Aviso de Segurança:**",
            "amenity_header": "📍 **Localização do Serviço mais Próximo:**",
            "transit_header": "🚌 **Trânsito e Transporte:**",
            "policies_header": "📖 **Diretrizes Oficiais do Estádio:**",
            "fallback_chat": f"Olá {name}! Sou o Setu, seu companheiro da Copa do Mundo FIFA 2026. A temperatura atual do estádio é {temp}°C.\n\nPergunte-me sobre como encontrar o banheiro mais próximo, portões menos cheios, opções de transporte ou políticas do estádio.",
            "wheelchair": "♿ Acessível para cadeira de rodas",
            "density": "Densidade da multidão"
        },
        "fr": {
            "title": "⚽ **Setu Companion — Mode de Secours en Direct**",
            "gates_header": "🗺️ **Portes Recommandées:**",
            "warnings_header": "⚠️ **Consignes de Sécurité:**",
            "amenity_header": "📍 **Emplacement du Service le plus Proche:**",
            "transit_header": "🚌 **Transport et Transit:**",
            "policies_header": "📖 **Directives Oficielles du Stade:**",
            "fallback_chat": f"Bonjour {name}! Je suis Setu, votre compagnon de la Coupe du Monde de la FIFA 2026. La température actuelle du stade est de {temp}°C.\n\nDemandez-moi pour trouver les toilettes les plus proches, les portes les moins encombrées, les options de transport ou les politiques du stade.",
            "wheelchair": "♿ Accessible en fauteuil roulant",
            "density": "Densité de la foule"
        },
        "ar": {
            "title": "⚽ **مرافق سيتو ليوم المباراة — وضع النسخ الاحتياطي المباشر**",
            "gates_header": "🗺️ **البوابات الموصى بها:**",
            "warnings_header": "⚠️ **تنبيه السلامة:**",
            "amenity_header": "📍 **موقع الخدمة الأقرب:**",
            "transit_header": "🚌 **النقل والمواصلات:**",
            "policies_header": "📖 **إرشادات الاستاد الرسمية:**",
            "fallback_chat": f"مرحباً {name}! أنا سيتو، مرافقك في كأس العالم FIFA 2026. درجة حرارة الاستاد الحالية هي {temp} درجة مئوية.\n\nاسألني عن موقع أقرب دورة مياه، أو البوابات الأقل ازدحاماً، أو خيارات النقل، أو سياسات الاستاد.",
            "wheelchair": "♿ متاح للكراسي المتحركة",
            "density": "كثافة الحشد"
        }
    }

    t = translations.get(language, translations["en"])
    parts = [t["title"]]

    # 1. Safety warnings
    if warnings:
        parts.append(f"{t['warnings_header']}\n" + "\n".join([f"- {w}" for w in warnings]))

    # 2. Gate recommendations
    if recommended_gates:
        gate_lines = []
        for g in recommended_gates:
            line = f"- **{g['name']}**: {t['density']} {g['crowd_density']}%"
            if g.get('distance'):
                line += f" ({g['distance']}m)"
            if g.get('wheelchair_accessible'):
                line += f" | {t['wheelchair']}"
            gate_lines.append(line)
        parts.append(f"{t['gates_header']}\n" + "\n".join(gate_lines))

    # 3. Amenity search
    if nearest_amenity:
        loc = nearest_amenity.get('location', {})
        dist = nearest_amenity.get('distance_m', 0)
        accessible = nearest_amenity.get('wheelchair_accessible', False)
        type_str = nearest_amenity.get('type', 'service')
        
        line = f"- **{type_str.capitalize()}** at Section {nearest_amenity.get('section', '?')} (Coordinates: {loc.get('x', 50)}, {loc.get('y', 50)})"
        if dist:
            line += f" — approx. {dist}m away"
        if accessible:
            line += f" | {t['wheelchair']}"
        parts.append(f"{t['amenity_header']}\n{line}")

    # 4. Policies
    if policies:
        policy_lines = [f"- {p}" for p in policies]
        parts.append(f"{t['policies_header']}\n" + "\n".join(policy_lines))

    # 5. Transit info
    if transit_info:
        parts.append(f"{t['transit_header']}\n- {transit_info}")

    # 6. Fallback general chat
    if len(parts) == 1:
        parts.append(t["fallback_chat"])

    return "\n\n".join(parts)


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
    except Exception:
        return _fallback_response(context, language)


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
    except Exception:
        # Graceful rule-based fallback streaming
        fallback_text = _fallback_response(context, language)
        # Yield the response in small chunks to simulate streaming
        chunk_size = 12
        for i in range(0, len(fallback_text), chunk_size):
            yield fallback_text[i:i+chunk_size]
