"""
test_decision_engine.py — Unit tests for the deterministic decision engine.

Tests:
  1. Wheelchair-needing fan never recommended a non-accessible gate
  2. Highest-crowd-density gate ranked lowest
  3. Closed gates excluded entirely
  4. Empty gates list → empty result (no crash)
  5. find_nearest_amenity correctness
  6. check_transit_recommendation logic
"""

import pytest

from backend.decision_engine import (
    check_transit_recommendation,
    find_nearest_amenity,
    rank_routes,
)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_gates():
    return [
        {"id": "G1", "name": "Gate A", "location": {"x": 50, "y": 10}, "crowd_density": 45, "wheelchair_accessible": True, "status": "open", "distance_from_common_entry": 0.2},
        {"id": "G2", "name": "Gate B", "location": {"x": 85, "y": 30}, "crowd_density": 72, "wheelchair_accessible": False, "status": "open", "distance_from_common_entry": 0.5},
        {"id": "G3", "name": "Gate C", "location": {"x": 90, "y": 60}, "crowd_density": 30, "wheelchair_accessible": True, "status": "open", "distance_from_common_entry": 0.7},
        {"id": "G4", "name": "Gate D", "location": {"x": 50, "y": 90}, "crowd_density": 95, "wheelchair_accessible": True, "status": "open", "distance_from_common_entry": 0.9},
        {"id": "G5", "name": "Gate E", "location": {"x": 10, "y": 60}, "crowd_density": 15, "wheelchair_accessible": True, "status": "open", "distance_from_common_entry": 0.6},
        {"id": "G7", "name": "Gate G", "location": {"x": 50, "y": 50}, "crowd_density": 20, "wheelchair_accessible": False, "status": "closed", "distance_from_common_entry": 0.8},
    ]


@pytest.fixture
def wheelchair_fan():
    return {"name": "Maria", "needs_wheelchair": True, "location": {"x": 45, "y": 20}}


@pytest.fixture
def regular_fan():
    return {"name": "Tom", "needs_wheelchair": False, "location": {"x": 30, "y": 70}}


@pytest.fixture
def sample_amenities():
    return [
        {"id": "A1", "name": "Restroom A", "type": "restroom", "location": {"x": 30, "y": 20}, "wheelchair_accessible": True},
        {"id": "A2", "name": "Restroom B", "type": "restroom", "location": {"x": 70, "y": 75}, "wheelchair_accessible": False},
        {"id": "A3", "name": "Medical North", "type": "medical", "location": {"x": 60, "y": 15}, "wheelchair_accessible": True},
    ]


# ── rank_routes tests ──────────────────────────────────────────────────

class TestRankRoutes:
    def test_wheelchair_fan_never_gets_inaccessible_gate(self, sample_gates, wheelchair_fan):
        """A wheelchair-needing fan must never be recommended a non-accessible gate."""
        result = rank_routes(wheelchair_fan, sample_gates)
        for gate in result:
            assert gate["wheelchair_accessible"] is True, (
                f"Gate {gate['name']} is not wheelchair-accessible but was recommended"
            )

    def test_highest_density_ranked_lowest(self, sample_gates, regular_fan):
        """The gate with the highest crowd density should be ranked last among open gates."""
        result = rank_routes(regular_fan, sample_gates)
        # Gate D has 95% density — should be last (or near last)
        # Among open gates only (Gate G is closed, excluded)
        assert len(result) > 0
        open_densities = [g["crowd_density"] for g in result]
        # Last gate in result should have the highest density
        assert result[-1]["crowd_density"] == max(open_densities)

    def test_closed_gates_excluded(self, sample_gates, regular_fan):
        """Closed gates must be excluded entirely from results."""
        result = rank_routes(regular_fan, sample_gates)
        gate_ids = {g["id"] for g in result}
        assert "G7" not in gate_ids, "Closed Gate G should have been excluded"

    def test_empty_gates_returns_empty(self, regular_fan):
        """Empty gates list must return empty list, not crash."""
        result = rank_routes(regular_fan, [])
        assert result == []

    def test_all_closed_gates_returns_empty(self, regular_fan):
        """If all gates are closed, return empty list."""
        gates = [
            {"id": "G1", "name": "Gate A", "location": {"x": 50, "y": 10}, "crowd_density": 20, "wheelchair_accessible": True, "status": "closed"},
        ]
        result = rank_routes(regular_fan, gates)
        assert result == []

    def test_result_sorted_by_score(self, sample_gates, regular_fan):
        """Results must be sorted by score (lowest = best) ascending."""
        result = rank_routes(regular_fan, sample_gates)
        scores = [g["score"] for g in result]
        assert scores == sorted(scores), "Results are not sorted by score"


# ── find_nearest_amenity tests ─────────────────────────────────────────

class TestFindNearestAmenity:
    def test_finds_nearest_restroom(self, sample_amenities):
        location = {"x": 25, "y": 25}
        result = find_nearest_amenity(location, "restroom", sample_amenities)
        assert result is not None
        assert result["id"] == "A1"  # closest to (25,25)

    def test_wheelchair_filter(self, sample_amenities):
        location = {"x": 65, "y": 70}
        result = find_nearest_amenity(location, "restroom", sample_amenities, needs_wheelchair=True)
        # Restroom B at (70,75) is closest but not accessible → should return A1
        assert result is not None
        assert result["wheelchair_accessible"] is True

    def test_nonexistent_type_returns_none(self, sample_amenities):
        location = {"x": 50, "y": 50}
        result = find_nearest_amenity(location, "swimming_pool", sample_amenities)
        assert result is None


# ── check_transit_recommendation tests ─────────────────────────────────

class TestTransitRecommendation:
    def test_short_distance_recommends_walk(self):
        result = check_transit_recommendation({"x": 50, "y": 50}, 0.5)
        assert result["mode"] == "walk"

    def test_medium_distance_recommends_transit(self):
        result = check_transit_recommendation({"x": 50, "y": 50}, 3.0)
        assert result["mode"] == "shuttle_or_metro"

    def test_long_distance_recommends_transit(self):
        result = check_transit_recommendation({"x": 50, "y": 50}, 10.0)
        assert result["mode"] == "shuttle_or_metro"
