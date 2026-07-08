"""
decision_engine.py — Deterministic core logic for Setu.

Pure Python, fully unit-testable. NO LLM calls inside this module.
Scores and ranks routes/gates for fans, finds nearest amenities,
and generates transit sustainability recommendations.
"""

from __future__ import annotations

import math
from typing import Any


def _euclidean_distance(p1: dict, p2: dict) -> float:
    """Calculate Euclidean distance between two 2D points."""
    return math.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2)


def rank_routes(fan_profile: dict, gates: list[dict], amenities: list[dict] | None = None) -> list[dict]:
    """
    Score and rank gates/routes for a fan based on:
      - crowd density          (lower is better — weight: 0.5)
      - distance from fan      (lower is better — weight: 0.3)
      - wheelchair access       (hard disqualifier if fan needs it and gate lacks it)
      - gate operational status (closed → excluded entirely)

    Returns a sorted list of viable gate dicts augmented with a ``score`` key
    (lower = better), best option first.  Returns an empty list gracefully
    when no viable gate exists.
    """
    if not gates:
        return []

    fan_location = fan_profile.get("location", {"x": 50, "y": 50})
    needs_wheelchair = fan_profile.get("needs_wheelchair", False)

    scored: list[dict] = []
    for gate in gates:
        # --- Hard exclusions ---
        if gate.get("status", "open") != "open":
            continue  # closed gates excluded entirely
        if needs_wheelchair and not gate.get("wheelchair_accessible", False):
            continue  # accessibility hard-disqualifier

        # --- Scoring (lower = better) ---
        crowd = gate.get("crowd_density", 0)  # 0-100
        dist = _euclidean_distance(fan_location, gate.get("location", {"x": 50, "y": 50}))
        # Normalise distance to 0-100 range (stadium grid is 100×100)
        max_possible = math.sqrt(100**2 + 100**2)  # ~141
        norm_dist = (dist / max_possible) * 100

        score = round(0.5 * crowd + 0.3 * norm_dist, 2)

        entry = {**gate, "score": score, "distance": round(dist, 2)}
        scored.append(entry)

    # Sort best (lowest score) first
    scored.sort(key=lambda g: g["score"])
    return scored


def find_nearest_amenity(
    fan_location: dict,
    amenity_type: str,
    amenities_list: list[dict],
    needs_wheelchair: bool = False,
) -> dict | None:
    """
    Return the single nearest amenity of ``amenity_type`` from the list.
    If the fan needs wheelchair access, filter out non-accessible amenities.
    Returns ``None`` if nothing matches.
    """
    candidates = [
        a for a in amenities_list
        if a.get("type", "").lower() == amenity_type.lower()
        and (not needs_wheelchair or a.get("wheelchair_accessible", False))
    ]
    if not candidates:
        return None

    best = min(candidates, key=lambda a: _euclidean_distance(fan_location, a.get("location", {"x": 50, "y": 50})))
    return {**best, "distance": round(_euclidean_distance(fan_location, best.get("location", {"x": 50, "y": 50})), 2)}


def check_transit_recommendation(fan_location: dict, distance_to_venue_km: float) -> dict:
    """
    Provide a sustainability-aware transit suggestion.

    Rules (simple heuristic):
    - distance <= 1 km   → walk
    - 1 < distance <= 5  → shuttle / metro
    - distance > 5       → shuttle / metro (with strong nudge away from driving)

    Returns a dict with ``mode`` and ``reason``.
    """
    if distance_to_venue_km <= 1.0:
        return {
            "mode": "walk",
            "reason": "You're close to the stadium! Walking is the fastest and greenest option.",
        }
    elif distance_to_venue_km <= 5.0:
        return {
            "mode": "shuttle_or_metro",
            "reason": (
                "A free shuttle or the metro line will get you there comfortably. "
                "Parking near the stadium is limited and congested on match days."
            ),
        }
    else:
        return {
            "mode": "shuttle_or_metro",
            "reason": (
                "We strongly recommend the free shuttle or metro — it's faster than "
                "driving and parking, and much better for the environment. "
                "Shuttle pick-ups run every 10 minutes from downtown transit hubs."
            ),
        }
