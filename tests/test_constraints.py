"""
tests/test_constraints.py
Comprehensive test suite verifying constraint-based reasoning edge cases:
1. Rejecting routes when transfer buffer < 5 minutes
2. Filtering out non-accessible stations when wheelchair mode is enabled
3. Failing gracefully with explanation when no route fits strict budget
4. Peak-hour crowding rules altering route rankings
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from knowledge_base.constraints import (
    WheelchairConstraint,
    BudgetConstraint,
    MaxTransfersConstraint,
    TransferBufferConstraint,
    PeakHourSoftConstraint,
    ModePreferenceSoftConstraint,
    TransferCountSoftConstraint,
)
from knowledge_base.rule_evaluator import RuleEvaluator


@pytest.fixture
def base_route():
    return {
        "stops": [
            {"stop_id": "CMRL-101", "stop_name": "Chennai Central", "wheelchair_accessible": True, "lat": 13.0827, "lon": 80.2707},
            {"stop_id": "CMRL-102", "stop_name": "Egmore", "wheelchair_accessible": True, "lat": 13.0784, "lon": 80.2612},
            {"stop_id": "CMRL-103", "stop_name": "Airport", "wheelchair_accessible": True, "lat": 12.9815, "lon": 80.1636},
        ],
        "legs": [
            {
                "mode": "Metro",
                "route_name": "Blue Line",
                "from_stop": "Chennai Central",
                "to_stop": "Egmore",
                "departure_time": "08:00",
                "arrival_time": "08:10",
                "fare": 20.0,
                "distance_km": 3.0,
            },
            {
                "mode": "Metro",
                "route_name": "Green Line",
                "from_stop": "Egmore",
                "to_stop": "Airport",
                "departure_time": "08:20",
                "arrival_time": "08:50",
                "fare": 40.0,
                "distance_km": 15.0,
            },
        ],
        "num_transfers": 1,
        "total_fare": 60.0,
        "total_time_mins": 50,
    }


# -------------------------------------------------------------------------
# Test Case 1: Transfer buffer constraint (< 5 mins rejected, >= 5 accepted)
# -------------------------------------------------------------------------
def test_transfer_buffer_rejection(base_route):
    constraint = TransferBufferConstraint()
    
    # Leg 1 arrives at 08:10, Leg 2 departs at 08:13 (Gap = 3 mins < 5 mins)
    base_route["legs"][1]["departure_time"] = "08:13"
    valid, msg = constraint.check(base_route, {})
    assert not valid, "Should reject route when transfer buffer < 5 minutes"
    assert "3 min gap" in msg
    assert "minimum 5 min required" in msg

    # Leg 1 arrives at 08:10, Leg 2 departs at 08:15 (Gap = 5 mins >= 5 mins)
    base_route["legs"][1]["departure_time"] = "08:15"
    valid, msg = constraint.check(base_route, {})
    assert valid, "Should accept route when transfer buffer is exactly 5 minutes"


# -------------------------------------------------------------------------
# Test Case 2: Wheelchair accessibility filter
# -------------------------------------------------------------------------
def test_wheelchair_accessibility(base_route):
    constraint = WheelchairConstraint()
    
    # When wheelchair_required is False, non-accessible stop is allowed
    base_route["stops"][1]["wheelchair_accessible"] = False
    valid, _ = constraint.check(base_route, {"wheelchair_required": False})
    assert valid, "Should pass when wheelchair accessibility is not required"

    # When wheelchair_required is True, non-accessible stop is rejected
    valid, msg = constraint.check(base_route, {"wheelchair_required": True})
    assert not valid, "Should reject route containing non-accessible station"
    assert "is not wheelchair-accessible" in msg


# -------------------------------------------------------------------------
# Test Case 3: Budget constraints and graceful failure
# -------------------------------------------------------------------------
def test_budget_constraint(base_route):
    constraint = BudgetConstraint()
    evaluator = RuleEvaluator()

    # Route costs ₹60. Budget is ₹100 -> Pass
    valid, _ = constraint.check(base_route, {"max_budget": 100.0})
    assert valid

    # Budget is ₹30 -> Fail with explicit reason
    valid, msg = constraint.check(base_route, {"max_budget": 30.0})
    assert not valid
    assert "exceeds budget ₹30.00" in msg

    # Full evaluator validation trace
    report = evaluator.validate(base_route, {"max_budget": 30.0, "wheelchair_required": False})
    assert not report["valid"]
    assert any("exceeds budget" in v for v in report["violations"])


# -------------------------------------------------------------------------
# Test Case 4: Peak hour rules alter ranking
# -------------------------------------------------------------------------
def test_peak_hour_soft_constraint_ranks(base_route):
    evaluator = RuleEvaluator()
    
    # Peak hour route (08:00 - 08:50)
    peak_route = dict(base_route)
    peak_route["id"] = "peak"
    
    # Off-peak route (11:00 - 11:50)
    off_peak_route = dict(base_route)
    off_peak_route["id"] = "off_peak"
    off_peak_route["legs"] = [
        dict(base_route["legs"][0], departure_time="11:00", arrival_time="11:10"),
        dict(base_route["legs"][1], departure_time="11:20", arrival_time="11:50"),
    ]

    prefs = {"priority_mode": "comfortable", "wheelchair_required": False, "max_budget": 100}
    
    ranked = evaluator.rank_routes([peak_route, off_peak_route], prefs, priority_mode="comfortable")
    
    # Off-peak route should rank higher (i.e. first) due to lower penalty
    assert ranked[0]["id"] == "off_peak", "Off-peak route should rank ahead of peak route"
