"""
Step 3 — API Integration Layer tests

Run:
    pytest src/tests/test_step3_api.py -v

Strategy
--------
Uses the real FastAPI `app` object with `app.dependency_overrides[get_db]`
to inject an isolated in-memory SQLite session for every test request.

Starlette 1.6.0 (installed) does NOT support `lifespan="off"` — the lifespan
always runs when TestClient is used as a context manager.  The lifespan writes
to `supply_chain.db` (which is in .gitignore).  All test requests use the
overridden `get_db` so assertions are fully isolated from the production file.

Test groups
-----------
S-xx   Shipment CRUD
R-xx   Risk Engine via API
CC-xx  Cold-Chain Engine via API
RO-xx  Route Optimizer via API
FM-xx  Fleet Matcher via API
D-xx   Disruption endpoints
FL-xx  Fleet data reads
RT-xx  Route data reads + JSON-text→list verification

Fixture constraints preserved
------------------------------
- SHP-1001 uses "Chicago Logistics Hub, IL" which does NOT match the route
  fixture "Chicago, IL"; therefore /routes returns no_route_found=true. Correct.
- FLT-514 is assigned to SHP-1003 and must NOT appear in its fleet-match results.
- FLT-302 is not asserted to rank first (CONFLICT-07).
- Risk scores are not persisted; calling /risk does not change /shipments data.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from src.backend.db.database import Base, get_db
from src.backend.db.seed import seed_database
from src.backend.main import app


# ---------------------------------------------------------------------------
# Shared test client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Build an isolated in-memory SQLite database, seed it, install a
    dependency override so every API request uses the test session, and
    yield a TestClient for the module.

    Teardown clears the override and closes the session.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False
    )
    test_session = TestSession()
    seed_database(test_session)

    def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
    test_session.close()


# ===========================================================================
# S — Shipment CRUD
# ===========================================================================

class TestShipmentCRUD:
    def test_s01_list_shipments(self, client):
        """GET /api/shipments → 200, 3 shipments."""
        resp = client.get("/api/shipments/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3
        ids = {s["id"] for s in body}
        assert ids == {"SHP-1001", "SHP-1002", "SHP-1003"}

    def test_s02_get_shp_1001(self, client):
        """GET /api/shipments/SHP-1001 → 200, correct origin."""
        resp = client.get("/api/shipments/SHP-1001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "SHP-1001"
        assert body["origin"] == "Chicago Logistics Hub, IL"
        assert body["cargo_type"] == "Pharmaceuticals"

    def test_s03_get_missing(self, client):
        """GET /api/shipments/SHP-NOTEXIST → 404."""
        resp = client.get("/api/shipments/SHP-NOTEXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_s04_get_shp_1002(self, client):
        """GET /api/shipments/SHP-1002 → 200, ALERT_DISRUPTION status."""
        resp = client.get("/api/shipments/SHP-1002")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "SHP-1002"
        assert body["status"] == "ALERT_DISRUPTION"


# ===========================================================================
# R — Risk Engine via API
# ===========================================================================

class TestRiskEngine:
    def test_r01_shp_1001_risk(self, client):
        """SHP-1001 risk → 200, score ≤ 50, severity LOW or MEDIUM."""
        resp = client.get("/api/shipments/SHP-1001/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shipment_id"] == "SHP-1001"
        assert 0.0 <= body["total_score"] <= 50.0
        assert body["severity"] in ("LOW", "MEDIUM")

    def test_r02_shp_1002_cold_contribution(self, client):
        """SHP-1002 has a warm excursion; r_cold_chain must be > 0."""
        resp = client.get("/api/shipments/SHP-1002/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["r_cold_chain"] > 0.0, (
            f"Expected r_cold_chain > 0 for SHP-1002 (warm excursion), "
            f"got {body['r_cold_chain']}"
        )

    def test_r03_missing_shipment(self, client):
        """GET /api/shipments/SHP-NOTEXIST/risk → 404."""
        resp = client.get("/api/shipments/SHP-NOTEXIST/risk")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_r04_active_risk_batch(self, client):
        """GET /api/risk/active → 200, 3 results."""
        resp = client.get("/api/risk/active")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3

    def test_r05_all_scores_in_range(self, client):
        """All active risk scores must be in [0, 100]."""
        resp = client.get("/api/risk/active")
        assert resp.status_code == 200
        for r in resp.json():
            assert 0.0 <= r["total_score"] <= 100.0, (
                f"Score out of range: {r['shipment_id']} = {r['total_score']}"
            )

    def test_r06_shp_1002_elevated_severity(self, client):
        """SHP-1002 should be at least MEDIUM risk."""
        resp = client.get("/api/shipments/SHP-1002/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["severity"] in ("MEDIUM", "HIGH", "CRITICAL"), (
            f"Expected at least MEDIUM for SHP-1002, got {body['severity']}"
        )

    def test_r07_sub_scores_in_range(self, client):
        """All sub-scores r_* must be in [0.0, 1.0]."""
        resp = client.get("/api/risk/active")
        assert resp.status_code == 200
        for r in resp.json():
            for key in ("r_disruption", "r_weather", "r_route", "r_cold_chain", "r_business"):
                assert 0.0 <= r[key] <= 1.0, (
                    f"{key} out of [0,1] for {r['shipment_id']}: {r[key]}"
                )

    def test_r08_risk_does_not_persist(self, client):
        """
        Calling /risk must not change the stored current_risk_score returned
        by /api/shipments/SHP-1001.
        """
        before = client.get("/api/shipments/SHP-1001").json()["current_risk_score"]
        client.get("/api/shipments/SHP-1001/risk")
        after = client.get("/api/shipments/SHP-1001").json()["current_risk_score"]
        assert before == after, (
            f"current_risk_score changed after /risk call: {before} → {after}"
        )


# ===========================================================================
# CC — Cold-Chain Engine via API
# ===========================================================================

class TestColdChain:
    def test_cc01_shp_1001_ok(self, client):
        """SHP-1001 (4.2°C within 2–8°C) → is_in_excursion=false, OK."""
        resp = client.get("/api/shipments/SHP-1001/cold-chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_in_excursion"] is False
        assert body["severity"] == "OK"
        assert body["shipment_id"] == "SHP-1001"

    def test_cc02_shp_1002_warm_excursion(self, client):
        """SHP-1002 (-17.2°C, max -18°C) → excursion WARNING, deviation > 0."""
        resp = client.get("/api/shipments/SHP-1002/cold-chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_in_excursion"] is True
        assert body["severity"] == "WARNING"
        assert body["deviation_c"] is not None
        assert body["deviation_c"] > 0.0, (
            f"Expected positive deviation for warm excursion, got {body['deviation_c']}"
        )

    def test_cc03_shp_1003_safe_cryo(self, client):
        """SHP-1003 (-71.4°C within -80 to -60°C) → no excursion."""
        resp = client.get("/api/shipments/SHP-1003/cold-chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_in_excursion"] is False

    def test_cc04_missing_shipment(self, client):
        """GET /api/shipments/SHP-NOTEXIST/cold-chain → 404."""
        resp = client.get("/api/shipments/SHP-NOTEXIST/cold-chain")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_cc05_grade_lookup(self, client):
        """SHP-1002 cargo_category='Perishable Frozen' must resolve correctly."""
        resp = client.get("/api/shipments/SHP-1002/cold-chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cargo_rule_found"] is True
        assert body["grade"] == "Perishable Frozen"
        assert body["allowed_min_c"] == -22.0
        assert body["allowed_max_c"] == -18.0


# ===========================================================================
# RO — Route Optimizer via API
# ===========================================================================

class TestRouteOptimizer:
    def test_ro01_shp_1002_route_result(self, client):
        """
        SHP-1002 origin is 'Seattle Port Terminals, WA'; the route fixture
        uses 'Seattle, WA'.  Exact string equality (MD-05) means no match.
        no_route_found=True is the correct 200 outcome for this shipment too.
        """
        resp = client.get("/api/shipments/SHP-1002/routes")
        assert resp.status_code == 200
        body = resp.json()
        # Both SHP-1001 and SHP-1002 origins don't match route fixture strings
        assert body["no_route_found"] is True
        assert body["scored_routes"] == []

    def test_ro02_shp_1001_no_route(self, client):
        """
        SHP-1001 origin 'Chicago Logistics Hub, IL' does not match any route
        origin 'Chicago, IL' (MD-05 exact string equality).
        no_route_found=true is the correct 200 outcome.
        """
        resp = client.get("/api/shipments/SHP-1001/routes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["no_route_found"] is True
        assert body["scored_routes"] == []

    def test_ro03_missing_shipment(self, client):
        """GET /api/shipments/SHP-NOTEXIST/routes → 404."""
        resp = client.get("/api/shipments/SHP-NOTEXIST/routes")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_ro04_icy_blocked_warning(self, client):
        """
        Uses a fresh isolated session with a synthetic shipment matching
        RT-SEA-DEN-01 ('Seattle, WA' → 'Denver, CO') to verify that the
        route optimizer returns the ICY_BLOCKED feasibility warning from
        WX-SEA-02.  Tests the engine logic that backs the API.
        """
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from sqlalchemy.pool import StaticPool
        from src.backend.db.database import Base
        from src.backend.db.seed import seed_database
        from src.backend.models.shipment import Shipment
        from src.backend.optimizer.route_optimizer import RouteOptimizer

        eng = _ce(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(eng)
        sess = _sm(bind=eng)()
        seed_database(sess)

        syn = Shipment(
            id="SHP-RO-API-ICY",
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
        sess.add(syn)
        sess.flush()

        result = RouteOptimizer(sess).optimize_for_shipment(syn)
        assert result.no_route_found is False
        all_warnings = [w for rs in result.scored_routes for w in rs.warnings]
        assert any("ICY_BLOCKED" in w for w in all_warnings), (
            f"Expected ICY_BLOCKED warning from WX-SEA-02, got: {all_warnings}"
        )
        sess.close()

    def test_ro05_score_bounds(self, client):
        """
        Score bounds check: use a synthetic matching shipment to get a non-empty
        scored_routes list and verify all scores are in [0.0, 1.0].
        """
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from sqlalchemy.pool import StaticPool
        from src.backend.db.database import Base
        from src.backend.db.seed import seed_database
        from src.backend.models.shipment import Shipment
        from src.backend.optimizer.route_optimizer import RouteOptimizer

        eng = _ce(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(eng)
        Sess = _sm(bind=eng)
        sess = Sess()
        seed_database(sess)

        syn = Shipment(
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
        sess.add(syn)
        sess.flush()

        opt = RouteOptimizer(sess)
        result = opt.optimize_for_shipment(syn)
        assert result.no_route_found is False

        for rs in result.scored_routes:
            assert 0.0 <= rs.total_score <= 1.0, (
                f"Route score out of bounds: {rs.route_id} = {rs.total_score}"
            )
        sess.close()

    def test_ro06_exactly_one_recommended(self, client):
        """
        Exactly one route must have recommended=True when multiple routes exist.
        Uses a synthetic matching shipment + engine directly (bypasses API since
        no fixture shipment origin matches a route origin exactly).
        """
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from sqlalchemy.pool import StaticPool
        from src.backend.db.database import Base
        from src.backend.db.seed import seed_database
        from src.backend.models.shipment import Shipment
        from src.backend.models.route import Route
        from src.backend.optimizer.route_optimizer import RouteOptimizer
        import json

        eng = _ce(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(eng)
        Sess = _sm(bind=eng)
        sess = Sess()
        seed_database(sess)

        # Add a second Seattle→Denver route so there are 2 candidates
        alt = Route(
            route_id="RT-SEA-DEN-ALT",
            name="Seattle to Denver Alt",
            origin="Seattle, WA",
            destination="Denver, CO",
            distance_km=2000.0,
            typical_duration_hours=19.0,
            highways=json.dumps(["US-2 E", "I-84 E"]),
        )
        sess.add(alt)

        syn = Shipment(
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
        sess.add(syn)
        sess.flush()

        opt = RouteOptimizer(sess)
        result = opt.optimize_for_shipment(syn)
        assert len(result.scored_routes) == 2

        recommended = [rs for rs in result.scored_routes if rs.recommended]
        assert len(recommended) == 1, (
            f"Expected exactly 1 recommended route, got {len(recommended)}"
        )
        best_score = max(rs.total_score for rs in result.scored_routes)
        assert abs(recommended[0].total_score - best_score) < 1e-9

        sess.close()


# ===========================================================================
# FM — Fleet Matcher via API
# ===========================================================================

class TestFleetMatcher:
    def test_fm01_flt514_excluded(self, client):
        """SHP-1003 fleet match: FLT-514 is assigned to SHP-1003 → not in results."""
        resp = client.get("/api/shipments/SHP-1003/fleet-match")
        assert resp.status_code == 200
        body = resp.json()
        assert body["no_asset_found"] is False
        asset_ids = [a["asset_id"] for a in body["scored_assets"]]
        assert "FLT-514" not in asset_ids, (
            "FLT-514 should not appear — it is the assigned vehicle for SHP-1003"
        )

    def test_fm02_cryo_shipment_low_compat(self, client):
        """All remaining assets are STANDARD_COLD; cargo_compat_score ≤ 0.1 for cryo."""
        resp = client.get("/api/shipments/SHP-1003/fleet-match")
        assert resp.status_code == 200
        for a in resp.json()["scored_assets"]:
            assert a["cargo_compat_score"] <= 0.1, (
                f"STANDARD_COLD asset {a['asset_id']} should have ≤ 0.1 compat "
                f"for ultra-cold shipment, got {a['cargo_compat_score']}"
            )

    def test_fm03_missing_shipment(self, client):
        """GET /api/shipments/SHP-NOTEXIST/fleet-match → 404."""
        resp = client.get("/api/shipments/SHP-NOTEXIST/fleet-match")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_fm04_shp_1001_fleet_match(self, client):
        """SHP-1001 fleet match returns results with scores in [0, 1]."""
        resp = client.get("/api/shipments/SHP-1001/fleet-match")
        assert resp.status_code == 200
        body = resp.json()
        assert body["no_asset_found"] is False
        for a in body["scored_assets"]:
            assert 0.0 <= a["total_score"] <= 1.0

    def test_fm05_exactly_one_recommended(self, client):
        """Exactly one asset in the result must have recommended=True."""
        resp = client.get("/api/shipments/SHP-1001/fleet-match")
        assert resp.status_code == 200
        body = resp.json()
        recommended_count = sum(
            1 for a in body["scored_assets"] if a["recommended"]
        )
        assert recommended_count == 1, (
            f"Expected exactly 1 recommended asset, got {recommended_count}"
        )


# ===========================================================================
# D — Disruption endpoints
# ===========================================================================

class TestDisruptions:
    def test_d01_list(self, client):
        """GET /api/disruptions → 200, 3 disruptions."""
        resp = client.get("/api/disruptions/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3
        ids = {d["id"] for d in body}
        assert ids == {"DIS-501", "DIS-502", "DIS-503"}

    def test_d02_get_dis_501(self, client):
        """GET /api/disruptions/DIS-501 → 200, SEVERE_WEATHER HIGH."""
        resp = client.get("/api/disruptions/DIS-501")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "DIS-501"
        assert body["type"] == "SEVERE_WEATHER"
        assert body["severity"] == "HIGH"

    def test_d03_missing_disruption(self, client):
        """GET /api/disruptions/DIS-NOTEXIST → 404."""
        resp = client.get("/api/disruptions/DIS-NOTEXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_d04_affected_shipments_dis503(self, client):
        """
        DIS-503 (PORT_CONTAINER_HOLD) → proximity_radius_km=50.0.
        Response structure is valid regardless of how many shipments are affected.
        """
        resp = client.get("/api/disruptions/DIS-503/affected-shipments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["disruption_id"] == "DIS-503"
        assert body["proximity_radius_km"] == 50.0  # PORT_CONTAINER_HOLD radius
        assert "affected_shipments" in body
        assert isinstance(body["affected_shipments"], list)

    def test_d05_affected_shipments_structure(self, client):
        """Each affected_shipment entry has required fields."""
        resp = client.get("/api/disruptions/DIS-503/affected-shipments")
        assert resp.status_code == 200
        for entry in resp.json()["affected_shipments"]:
            assert "shipment_id" in entry
            assert "distance_km" in entry
            assert "shipment_status" in entry

    def test_d06_affected_shipments_dis501(self, client):
        """DIS-501 (SEVERE_WEATHER) → proximity_radius_km=200.0."""
        resp = client.get("/api/disruptions/DIS-501/affected-shipments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proximity_radius_km"] == 200.0
        assert body["disruption_type"] == "SEVERE_WEATHER"

    def test_d07_affected_shipments_missing_disruption(self, client):
        """GET /api/disruptions/DIS-NOTEXIST/affected-shipments → 404."""
        resp = client.get("/api/disruptions/DIS-NOTEXIST/affected-shipments")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_d08_dis502_roadwork_radius(self, client):
        """DIS-502 (ROADWORK_CONGESTION) → proximity_radius_km=30.0."""
        resp = client.get("/api/disruptions/DIS-502/affected-shipments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proximity_radius_km"] == 30.0


# ===========================================================================
# FL — Fleet data reads
# ===========================================================================

class TestFleetData:
    def test_fl01_list_fleet(self, client):
        """GET /api/fleet → 200, 3 assets."""
        resp = client.get("/api/fleet/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3
        ids = {a["id"] for a in body}
        assert ids == {"FLT-302", "FLT-109", "FLT-514"}

    def test_fl02_get_flt514(self, client):
        """GET /api/fleet/FLT-514 → 200, correct vehicle_type."""
        resp = client.get("/api/fleet/FLT-514")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "FLT-514"
        assert body["vehicle_type"] == "Specialized Cryo-Reefer Van"

    def test_fl03_missing_fleet_asset(self, client):
        """GET /api/fleet/FLT-NOTEXIST → 404."""
        resp = client.get("/api/fleet/FLT-NOTEXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ===========================================================================
# RT — Route data reads + JSON text → list serialization
# ===========================================================================

class TestRouteData:
    def test_rt01_list_routes(self, client):
        """GET /api/routes → 200, 2 routes."""
        resp = client.get("/api/routes/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2
        ids = {r["route_id"] for r in body}
        assert ids == {"RT-CHI-ATL-01", "RT-SEA-DEN-01"}

    def test_rt02_get_sea_den_route(self, client):
        """GET /api/routes/RT-SEA-DEN-01 → 200, highways is a list."""
        resp = client.get("/api/routes/RT-SEA-DEN-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["route_id"] == "RT-SEA-DEN-01"
        assert isinstance(body["highways"], list), (
            f"Expected highways to be a list, got {type(body['highways'])}"
        )
        assert "I-90 E" in body["highways"]

    def test_rt03_missing_route(self, client):
        """GET /api/routes/RT-NOTEXIST → 404."""
        resp = client.get("/api/routes/RT-NOTEXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_rt04_all_routes_highways_are_lists(self, client):
        """
        Validates the field_validator fix in schemas/route.py.
        All routes in the list response must return highways as a Python list,
        not as a raw JSON string.
        """
        resp = client.get("/api/routes/")
        assert resp.status_code == 200
        for route in resp.json():
            assert isinstance(route["highways"], list), (
                f"Route {route['route_id']} highways is not a list: "
                f"{type(route['highways'])} = {route['highways']!r}"
            )

    def test_rt05_waypoints_are_lists(self, client):
        """Route waypoints must be deserialized to lists of dicts, not raw JSON."""
        resp = client.get("/api/routes/RT-CHI-ATL-01")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["waypoints"], list), (
            f"waypoints should be a list, got {type(body['waypoints'])}"
        )
        assert len(body["waypoints"]) > 0
        # Each waypoint should be a dict with at least 'name', 'lat', 'lon'
        wp = body["waypoints"][0]
        assert "name" in wp
        assert "lat" in wp
        assert "lon" in wp
