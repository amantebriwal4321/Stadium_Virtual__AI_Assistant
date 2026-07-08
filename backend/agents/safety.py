"""
safety.py — Safety Agent (pure Python rules engine, NO LLM).

This agent applies hard safety rules deterministically and cannot be
manipulated by prompt injection.  It vets the decision engine's output
and can veto or reroute recommendations.
"""

from __future__ import annotations

from typing import Any

# Crowd-density threshold above which a gate is vetoed (too crowded)
CROWD_DENSITY_THRESHOLD = 85  # percent

# Temperature thresholds (°C)
HEAT_WARNING_THRESHOLD = 35   # advisory: hydrate, seek shade
HEAT_DANGER_THRESHOLD = 42    # danger: cooling stations, medical standby

# Emergency response protocol — returned immediately, bypassing everything
EMERGENCY_PROTOCOL = {
    "action": "emergency_protocol",
    "message": (
        "🚨 EMERGENCY PROTOCOL ACTIVATED. "
        "Stay calm. Follow the illuminated exit signs. Do NOT use elevators. "
        "Move to the nearest open gate and proceed to the assembly point in "
        "the outer parking lots. Follow steward instructions at all times."
    ),
    "gates_vetoed": [],
    "rerouted": False,
}


def evaluate(
    *,
    intent: str,
    ranked_gates: list[dict],
    fan_profile: dict,
    urgency: str = "low",
    temperature_c: float = 28.0,
) -> dict:
    """
    Apply deterministic safety rules to the ranked gates list.

    Returns a safety decision dict:
    {
        "action": "allow" | "reroute" | "veto_all" | "emergency_protocol",
        "approved_gates": [...],
        "gates_vetoed": [...],
        "rerouted": bool,
        "warnings": [str, ...],
        "message": str | None,
        "temperature_c": float,
        "heat_level": "normal" | "warning" | "danger",
    }
    """
    # --- Emergency intent: bypass everything ---
    if intent == "emergency" or urgency == "critical":
        return {**EMERGENCY_PROTOCOL}

    warnings: list[str] = []
    approved: list[dict] = []
    vetoed: list[dict] = []
    rerouted = False

    # --- Temperature rules (stadium-wide) ---
    heat_level = "normal"
    if temperature_c >= HEAT_DANGER_THRESHOLD:
        heat_level = "danger"
        warnings.append(
            f"🌡️ EXTREME HEAT ALERT: {temperature_c}°C. Cooling stations activated. "
            f"Free water at all gates. Seek shade immediately and visit the nearest medical tent "
            f"if you feel dizzy or nauseous."
        )
    elif temperature_c >= HEAT_WARNING_THRESHOLD:
        heat_level = "warning"
        warnings.append(
            f"🌡️ Heat advisory: {temperature_c}°C. Stay hydrated, wear sun protection, "
            f"and take breaks in shaded concourse areas."
        )

    for gate in ranked_gates:
        density = gate.get("crowd_density", 0)
        accessible = gate.get("wheelchair_accessible", False)
        needs_wheelchair = fan_profile.get("needs_wheelchair", False)

        # Rule 1: veto overcrowded gates
        if density > CROWD_DENSITY_THRESHOLD:
            vetoed.append(gate)
            warnings.append(
                f"{gate['name']} vetoed: crowd density {density}% exceeds {CROWD_DENSITY_THRESHOLD}% safety threshold."
            )
            rerouted = True
            continue

        # Rule 2: wheelchair-accessibility disqualifier
        # (decision_engine should already filter these, but defence-in-depth)
        if needs_wheelchair and not accessible:
            vetoed.append(gate)
            warnings.append(
                f"{gate['name']} vetoed: not wheelchair-accessible."
            )
            continue

        approved.append(gate)

    if not approved:
        return {
            "action": "veto_all",
            "approved_gates": [],
            "gates_vetoed": vetoed,
            "rerouted": rerouted,
            "warnings": warnings,
            "temperature_c": temperature_c,
            "heat_level": heat_level,
            "message": (
                "All nearby gates are currently unsafe or inaccessible. "
                "Please wait in a safe area and follow steward instructions."
            ),
        }

    return {
        "action": "reroute" if rerouted else "allow",
        "approved_gates": approved,
        "gates_vetoed": vetoed,
        "rerouted": rerouted,
        "warnings": warnings,
        "temperature_c": temperature_c,
        "heat_level": heat_level,
        "message": None,
    }
