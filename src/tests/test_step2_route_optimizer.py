"""
Step 2 — Route Optimizer tests

Run:
    pytest src/tests/test_step2_route_optimizer.py -v

Coverage:
    RO-01  Disruption penalizes route (RT-SEA-DEN-01 vs DIS-501 I-90 match)
    RO-02  Blocked weather penalizes route (ICY_BLOCKED warning present)
    RO-03  Scores bounded [0, 1]
    RO-04  Single-route safe normalization → total_score == 1.0
    RO-05  Formula weight invariant
    RO-06  Recommended route is highest-scoring
    RO-07  No route for shipment → no_route_found=True, scored_routes=[]
    RO-08  Unrelated route not evaluated for SHP-1001 (Chicago→Atlanta)
    RO-09  Equal-min/max normalizer safety (no division-by-zero)
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from src.backend.db.database import Base
from src.backend.db.seed import seed_database
from src.backend.models.shipment import Shipment
from src.backend.optimizer.route_optimizer import (
    RouteOptimizer,
    W_ETA,
    W_COST,
    W_DISRUPTION,
    W_WEATHER,
    W_COLD_CHAIN,
)
from src.backend.optimizer.normalizer import min_max_normalize

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_database(session)
    yield session
    session.close()


# ---------------------------------------------------------------------------
# RO-05 — Weight invariant
# ---------------------------------------------------------------------------

def test_ro05_weight_invariant():
    total = W_ETA + W_COST + W_DISRUPTION + W_WEATHER + W_COLD_CHAIN
    assert abs(total - 1.0) < 1e-9, f"Route weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# RO-09 — Normalizer edge case: equal values / single value
# ---------------------------------------------------------------------------

def test_ro09_normalizer_equal_values():
    result = min_max_normalize([5.0, 5.0, 5.0])
    assert result == [0.0, 0.0, 0.0]


def test_ro09_normalizer_single_value():
    result = min_max_normalize([42.0])
    assert result == [0.0]


def test_ro09_normalizer_empty_raises():
    with pytest.raises(ValueError):
        min_max_normalize([])


def test_ro09_normalizer_normal():
    result = min_max_normalize([0.0, 5.0, 10.0])
    assert abs(result[0] - 0.0) < 1e-9
    assert abs(result[1] - 0.5) < 1e-9
    assert abs(result[2] - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# RO-07 — No matching route → no_route_found=True
# ---------------------------------------------------------------------------

def test_ro07_no_route_found(db_session):
    unknown_shp = Shipment(
        id="SHP-RO-NOROUTE",
        origin="Fakeville, ZZ",
        destination="Otherville, QQ",
        cargo_type="Pharmaceuticals",
        cargo_category="Cold Chain Grade A",
        required_temp_min_c=2.0,
        required_temp_max_c=8.0,
        status="IN_TRANSIT",
    )
    db_session.add(unknown_shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(unknown_shp)
    assert result.no_route_found is True
    assert result.scored_routes == []

    db_session.delete(unknown_shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# RO-08 — SHP-1001 only evaluates Chicago→Atlanta route
# ---------------------------------------------------------------------------

def test_ro08_only_matching_route_evaluated(db_session):
    shp = db_session.get(Shipment, "SHP-1001")
    # SHP-1001: origin="Chicago Logistics Hub, IL" / dest="Atlanta Distribution Center, GA"
    # This does NOT match any route in fixture (routes use "Chicago, IL" / "Atlanta, GA")
    # So this should return no_route_found=True
    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(shp)
    # Exact string match: "Chicago Logistics Hub, IL" ≠ "Chicago, IL"
    # Therefore no routes match → no_route_found=True
    assert result.no_route_found is True
    # Confirm RT-SEA-DEN-01 is NOT in results
    for rs in result.scored_routes:
        assert rs.route_id != "RT-SEA-DEN-01", (
            "Seattle→Denver route should not appear for a Chicago→Atlanta shipment"
        )


# ---------------------------------------------------------------------------
# RO-04 — Single-route: hat=0 for all factors → total_score=1.0
# ---------------------------------------------------------------------------

def test_ro04_single_route_normalization(db_session):
    # Inject a shipment that matches RT-SEA-DEN-01 (Seattle→Denver)
    single_route_shp = Shipment(
        id="SHP-RO-SINGLE",
        origin="Seattle, WA",
        destination="Denver, CO",
        cargo_type="Fresh Seafood",
        cargo_category="Perishable Frozen",
        required_temp_min_c=-22.0,
        required_temp_max_c=-18.0,
        status="IN_TRANSIT",
        current_lat=45.5152,
        current_lon=-122.6784,
    )
    db_session.add(single_route_shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(single_route_shp)
    # Should find exactly RT-SEA-DEN-01
    assert result.no_route_found is False
    assert len(result.scored_routes) == 1
    rs = result.scored_routes[0]
    assert rs.route_id == "RT-SEA-DEN-01"
    # With a single candidate all hats=0 → total_score = sum(w × 1.0) = 1.0
    assert abs(rs.total_score - 1.0) < 1e-9, (
        f"Expected total_score=1.0 for single route, got {rs.total_score}"
    )
    assert rs.recommended is True

    db_session.delete(single_route_shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# RO-01 — Disruption penalizes RT-SEA-DEN-01 (I-90 overlap with DIS-501)
# ---------------------------------------------------------------------------

def test_ro01_disruption_penalizes_route(db_session):
    # RT-SEA-DEN-01 has highways ["I-90 E", ...]; DIS-501 affected_corridor = "I-90 Eastbound"
    # This should produce disruption_factor > 0 when there are two comparable routes.
    # We inject a clean "dummy" route to compare against.
    from src.backend.models.route import Route
    import json

    clean_route = Route(
        route_id="RT-SEA-DEN-CLEAN",
        name="Seattle to Denver Clean Route",
        origin="Seattle, WA",
        destination="Denver, CO",
        distance_km=2200.0,
        typical_duration_hours=21.0,
        highways=json.dumps(["I-5 S", "I-84 E"]),  # no I-90
    )
    db_session.add(clean_route)

    shp = Shipment(
        id="SHP-RO-DISRUPT",
        origin="Seattle, WA",
        destination="Denver, CO",
        cargo_type="Fresh Seafood",
        cargo_category="Perishable Frozen",
        required_temp_min_c=-22.0,
        required_temp_max_c=-18.0,
        status="IN_TRANSIT",
        current_lat=45.5152,
        current_lon=-122.6784,
    )
    db_session.add(shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(shp)
    assert result.no_route_found is False

    route_ids = [rs.route_id for rs in result.scored_routes]
    assert "RT-SEA-DEN-01" in route_ids
    assert "RT-SEA-DEN-CLEAN" in route_ids

    sea_den_score = next(rs for rs in result.scored_routes if rs.route_id == "RT-SEA-DEN-01")
    clean_score = next(rs for rs in result.scored_routes if rs.route_id == "RT-SEA-DEN-CLEAN")

    # RT-SEA-DEN-01 has I-90 overlap → higher raw disruption exposure → lower score
    # (1 - hat) is smaller for the disrupted route after normalization
    assert sea_den_score.disruption_factor >= clean_score.disruption_factor, (
        "RT-SEA-DEN-01 should have higher disruption hat than the clean alternative"
    )

    db_session.delete(clean_route)
    db_session.delete(shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# RO-02 — Blocked weather yields warning
# ---------------------------------------------------------------------------

def test_ro02_icy_blocked_warning(db_session):
    # WX-SEA-02 has road_condition=ICY_BLOCKED → any route should get a warning
    shp = Shipment(
        id="SHP-RO-WEATHER",
        origin="Seattle, WA",
        destination="Denver, CO",
        cargo_type="Fresh Seafood",
        cargo_category="Perishable Frozen",
        required_temp_min_c=-22.0,
        required_temp_max_c=-18.0,
        status="IN_TRANSIT",
        current_lat=45.5152,
        current_lon=-122.6784,
    )
    db_session.add(shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(shp)
    assert result.no_route_found is False

    # At least one route should have an ICY_BLOCKED warning
    all_warnings = [w for rs in result.scored_routes for w in rs.warnings]
    has_icy_warning = any("ICY_BLOCKED" in w for w in all_warnings)
    assert has_icy_warning, (
        "Expected at least one ICY_BLOCKED feasibility warning from WX-SEA-02"
    )

    db_session.delete(shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# RO-03 — All scores bounded [0, 1]
# ---------------------------------------------------------------------------

def test_ro03_score_bounds(db_session):
    shp = Shipment(
        id="SHP-RO-BOUNDS",
        origin="Seattle, WA",
        destination="Denver, CO",
        cargo_type="Fresh Seafood",
        cargo_category="Perishable Frozen",
        required_temp_min_c=-22.0,
        required_temp_max_c=-18.0,
        status="IN_TRANSIT",
        current_lat=45.5152,
        current_lon=-122.6784,
    )
    db_session.add(shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(shp)
    for rs in result.scored_routes:
        assert 0.0 <= rs.total_score <= 1.0, (
            f"Route score out of bounds: {rs.route_id} = {rs.total_score}"
        )

    db_session.delete(shp)
    db_session.flush()


# ---------------------------------------------------------------------------
# RO-06 — Recommended route is highest-scoring
# ---------------------------------------------------------------------------

def test_ro06_recommended_is_highest(db_session):
    from src.backend.models.route import Route
    import json

    alt_route = Route(
        route_id="RT-SEA-DEN-ALT",
        name="Seattle to Denver Alt",
        origin="Seattle, WA",
        destination="Denver, CO",
        distance_km=2000.0,
        typical_duration_hours=19.0,
        highways=json.dumps(["US-2 E", "I-90 E"]),
    )
    db_session.add(alt_route)

    shp = Shipment(
        id="SHP-RO-RECOM",
        origin="Seattle, WA",
        destination="Denver, CO",
        cargo_type="Fresh Seafood",
        cargo_category="Perishable Frozen",
        required_temp_min_c=-22.0,
        required_temp_max_c=-18.0,
        status="IN_TRANSIT",
        current_lat=45.5152,
        current_lon=-122.6784,
    )
    db_session.add(shp)
    db_session.flush()

    optimizer = RouteOptimizer(db_session)
    result = optimizer.optimize_for_shipment(shp)
    assert len(result.scored_routes) >= 2

    recommended = [rs for rs in result.scored_routes if rs.recommended]
    assert len(recommended) == 1, f"Expected exactly 1 recommended route, got {len(recommended)}"

    best_score = max(rs.total_score for rs in result.scored_routes)
    assert abs(recommended[0].total_score - best_score) < 1e-9

    db_session.delete(alt_route)
    db_session.delete(shp)
    db_session.flush()
