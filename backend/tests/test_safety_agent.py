"""
test_safety_agent.py — Unit tests for the deterministic Safety Agent.

Tests:
  1. crowd_density > 85% triggers a reroute veto
  2. Emergency intent returns emergency protocol immediately
  3. Wheelchair fan blocks non-accessible gates
  4. All-vetoed scenario returns veto_all action
"""

import pytest

from backend.agents.safety import CROWD_DENSITY_THRESHOLD, evaluate


@pytest.fixture
def gates_with_overcrowded():
    """Includes a gate above the 85% threshold."""
    return [
        {"id": "G1", "name": "Gate A", "crowd_density": 45, "wheelchair_accessible": True, "status": "open"},
        {"id": "G4", "name": "Gate D", "crowd_density": 90, "wheelchair_accessible": True, "status": "open"},
        {"id": "G5", "name": "Gate E", "crowd_density": 15, "wheelchair_accessible": True, "status": "open"},
    ]


@pytest.fixture
def regular_fan():
    return {"name": "Tom", "needs_wheelchair": False, "location": {"x": 30, "y": 70}}


@pytest.fixture
def wheelchair_fan():
    return {"name": "Maria", "needs_wheelchair": True, "location": {"x": 45, "y": 20}}


class TestSafetyAgent:
    def test_overcrowded_gate_vetoed(self, gates_with_overcrowded, regular_fan):
        """Gates with crowd_density > 85% must be vetoed."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
        )
        vetoed_ids = {g["id"] for g in result["gates_vetoed"]}
        assert "G4" in vetoed_ids, "Gate D (90% density) should have been vetoed"
        assert result["rerouted"] is True

    def test_approved_gates_below_threshold(self, gates_with_overcrowded, regular_fan):
        """Gates below the threshold should be approved."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
        )
        approved_ids = {g["id"] for g in result["approved_gates"]}
        assert "G1" in approved_ids
        assert "G5" in approved_ids

    def test_emergency_intent_returns_protocol(self, gates_with_overcrowded, regular_fan):
        """Emergency intent must bypass everything and return protocol."""
        result = evaluate(
            intent="emergency",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
        )
        assert result["action"] == "emergency_protocol"
        assert "EMERGENCY" in result["message"]

    def test_critical_urgency_returns_protocol(self, gates_with_overcrowded, regular_fan):
        """Critical urgency must also trigger emergency protocol."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
            urgency="critical",
        )
        assert result["action"] == "emergency_protocol"

    def test_wheelchair_non_accessible_vetoed(self, wheelchair_fan):
        """Non-accessible gates must be vetoed for wheelchair users."""
        gates = [
            {"id": "G2", "name": "Gate B", "crowd_density": 30, "wheelchair_accessible": False, "status": "open"},
            {"id": "G3", "name": "Gate C", "crowd_density": 25, "wheelchair_accessible": True, "status": "open"},
        ]
        result = evaluate(
            intent="navigation",
            ranked_gates=gates,
            fan_profile=wheelchair_fan,
        )
        approved_ids = {g["id"] for g in result["approved_gates"]}
        assert "G2" not in approved_ids
        assert "G3" in approved_ids

    def test_all_gates_vetoed(self, wheelchair_fan):
        """When every gate is unsafe or inaccessible, return veto_all."""
        gates = [
            {"id": "G1", "name": "Gate A", "crowd_density": 95, "wheelchair_accessible": True, "status": "open"},
            {"id": "G2", "name": "Gate B", "crowd_density": 90, "wheelchair_accessible": False, "status": "open"},
        ]
        result = evaluate(
            intent="navigation",
            ranked_gates=gates,
            fan_profile=wheelchair_fan,
        )
        assert result["action"] == "veto_all"
        assert len(result["approved_gates"]) == 0

    def test_threshold_constant(self):
        """Verify the crowd-density threshold is 85%."""
        assert CROWD_DENSITY_THRESHOLD == 85

    def test_normal_temperature_no_warning(self, gates_with_overcrowded, regular_fan):
        """Temperature below 35°C should produce heat_level='normal' with no heat warning."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
            temperature_c=28.0,
        )
        assert result["heat_level"] == "normal"
        assert not any("Heat advisory" in w for w in result["warnings"])
        assert not any("EXTREME HEAT" in w for w in result["warnings"])

    def test_heat_warning_at_35c(self, gates_with_overcrowded, regular_fan):
        """Temperature >= 35°C should trigger heat_level='warning' with advisory."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
            temperature_c=37.0,
        )
        assert result["heat_level"] == "warning"
        assert result["temperature_c"] == 37.0
        heat_warnings = [w for w in result["warnings"] if "Heat advisory" in w]
        assert len(heat_warnings) == 1

    def test_extreme_heat_at_42c(self, gates_with_overcrowded, regular_fan):
        """Temperature >= 42°C should trigger heat_level='danger' with extreme alert."""
        result = evaluate(
            intent="navigation",
            ranked_gates=gates_with_overcrowded,
            fan_profile=regular_fan,
            temperature_c=44.0,
        )
        assert result["heat_level"] == "danger"
        assert result["temperature_c"] == 44.0
        extreme_warnings = [w for w in result["warnings"] if "EXTREME HEAT" in w]
        assert len(extreme_warnings) == 1
