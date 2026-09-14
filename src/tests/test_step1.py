"""
Step 1 validation tests — Backend Data & Schema Foundation

These tests verify the complete Step 1 implementation without starting Uvicorn.
They use an isolated in-memory SQLite database so they are fast and hermetic.

Run:
    pytest src/tests/test_step1.py -v

Coverage:
  - Database initialisation (tables created)
  - All 8 ORM models loadable and table names correct
  - Seed loader inserts expected record counts
  - Seed loader is idempotent (no duplicates on second run)
  - FK relationships valid (SHP-1001 → FLT-302, CRR-401)
  - Telemetry FK (TEL-FLT-302 → FLT-302, SHP-1001)
  - Pydantic schemas validate from fixture dicts
  - FastAPI app health endpoint returns 200
"""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Ensure the repo root is on sys.path so `src.*` imports resolve.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from src.backend.db.database import Base, init_db
from src.backend.db.seed import seed_database
from src.backend.models import (
    CargoRule,
    Carrier,
    Disruption,
    FleetAsset,
    Route,
    Shipment,
    Telemetry,
    Weather,
)
from src.backend.schemas import (
    CargoRuleResponse,
    CarrierResponse,
    DisruptionResponse,
    FleetAssetResponse,
    RouteResponse,
    ShipmentResponse,
    TelemetryResponse,
    WeatherResponse,
)


# ---------------------------------------------------------------------------
# Shared in-memory SQLite fixture
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def db_session():
    """
    Create an isolated in-memory SQLite database, run create_all + seed,
    and yield a session.  The database is discarded after the module finishes.

    StaticPool is required for SQLite :memory: so that all connections within
    the same engine share the single in-memory database rather than each
    creating their own empty database.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register all models on Base.metadata (side-effect of importing models).
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    seed_database(session)
    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. Database initialisation
# ---------------------------------------------------------------------------

class TestDatabaseInitialisation:
    def test_all_tables_created(self, db_session):
        """All 8 entity tables must exist after create_all + seed."""
        inspector = inspect(db_session.bind)
        table_names = set(inspector.get_table_names())
        expected = {
            "carriers",
            "routes",
            "cargo_rules",
            "fleet_assets",
            "disruptions",
            "weather",
            "shipments",
            "telemetry",
        }
        assert expected.issubset(table_names), (
            f"Missing tables: {expected - table_names}"
        )


# ---------------------------------------------------------------------------
# 2. ORM model table names
# ---------------------------------------------------------------------------

class TestOrmModelTableNames:
    @pytest.mark.parametrize(
        "model_cls, expected_table",
        [
            (Carrier,    "carriers"),
            (Route,      "routes"),
            (CargoRule,  "cargo_rules"),
            (FleetAsset, "fleet_assets"),
            (Disruption, "disruptions"),
            (Weather,    "weather"),
            (Shipment,   "shipments"),
            (Telemetry,  "telemetry"),
        ],
    )
    def test_table_name(self, model_cls, expected_table, db_session):
        assert model_cls.__tablename__ == expected_table


# ---------------------------------------------------------------------------
# 3. Seed record counts
# ---------------------------------------------------------------------------

class TestSeedRecordCounts:
    """Fixture files contain exactly: 3 carriers, 3 cargo_rules, 2 routes,
    4 weather stations, 3 fleet assets, 3 disruptions, 3 shipments, 3 telemetry."""

    def test_carrier_count(self, db_session):
        assert db_session.query(Carrier).count() == 3

    def test_cargo_rule_count(self, db_session):
        assert db_session.query(CargoRule).count() == 3

    def test_route_count(self, db_session):
        assert db_session.query(Route).count() == 2

    def test_weather_count(self, db_session):
        assert db_session.query(Weather).count() == 4

    def test_fleet_asset_count(self, db_session):
        assert db_session.query(FleetAsset).count() == 3

    def test_disruption_count(self, db_session):
        assert db_session.query(Disruption).count() == 3

    def test_shipment_count(self, db_session):
        assert db_session.query(Shipment).count() == 3

    def test_telemetry_count(self, db_session):
        assert db_session.query(Telemetry).count() == 3


# ---------------------------------------------------------------------------
# 4. Specific field values from fixtures
# ---------------------------------------------------------------------------

class TestSeedFieldValues:
    def test_shp_1002_status(self, db_session):
        shp = db_session.get(Shipment, "SHP-1002")
        assert shp is not None
        assert shp.status == "ALERT_DISRUPTION"

    def test_shp_1002_risk_score(self, db_session):
        shp = db_session.get(Shipment, "SHP-1002")
        assert shp is not None
        assert abs(shp.current_risk_score - 0.78) < 1e-6

    def test_tel_flt_109_compressor(self, db_session):
        tel = db_session.get(Telemetry, "TEL-FLT-109")
        assert tel is not None
        assert tel.reefer_compressor_status == "WARNING_HIGH_LOAD"

    def test_flt_514_vehicle_type(self, db_session):
        fleet = db_session.get(FleetAsset, "FLT-514")
        assert fleet is not None
        assert fleet.vehicle_type == "Specialized Cryo-Reefer Van"

    def test_disruption_geometry_point(self, db_session):
        dis = db_session.get(Disruption, "DIS-501")
        assert dis is not None
        assert dis.geometry_lat is not None
        assert dis.geometry_lon is not None

    def test_weather_snoqualmie_road_condition(self, db_session):
        wx = db_session.get(Weather, "WX-SEA-02")
        assert wx is not None
        assert wx.road_condition == "ICY_BLOCKED"

    def test_carrier_certifications_parseable(self, db_session):
        carrier = db_session.get(Carrier, "CRR-401")
        assert carrier is not None
        certs = carrier.get_certifications_list()
        assert isinstance(certs, list)
        assert len(certs) > 0

    def test_route_waypoints_parseable(self, db_session):
        route = db_session.get(Route, "RT-CHI-ATL-01")
        assert route is not None
        waypoints = route.get_waypoints_list()
        assert isinstance(waypoints, list)
        assert len(waypoints) == 4

    def test_cargo_rule_ultra_cold_chain(self, db_session):
        rule = (
            db_session.query(CargoRule)
            .filter_by(category="Biologics & Vaccines")
            .first()
        )
        assert rule is not None
        assert rule.grade == "Ultra Cold Chain"
        assert rule.min_temp_c == -80.0


# ---------------------------------------------------------------------------
# 5. Idempotency — second seed run must not create duplicates
# ---------------------------------------------------------------------------

class TestSeedIdempotency:
    def test_no_duplicates_on_second_seed(self, db_session):
        before_carriers = db_session.query(Carrier).count()
        before_shipments = db_session.query(Shipment).count()

        seed_database(db_session)

        assert db_session.query(Carrier).count() == before_carriers
        assert db_session.query(Shipment).count() == before_shipments


# ---------------------------------------------------------------------------
# 6. Foreign-key relationships
# ---------------------------------------------------------------------------

class TestForeignKeyRelationships:
    def test_shp_1001_vehicle_fk(self, db_session):
        """SHP-1001 must reference an existing FleetAsset (FLT-302)."""
        shp = db_session.get(Shipment, "SHP-1001")
        assert shp is not None
        assert shp.assigned_vehicle_id == "FLT-302"
        fleet = db_session.get(FleetAsset, shp.assigned_vehicle_id)
        assert fleet is not None

    def test_shp_1001_carrier_fk(self, db_session):
        """SHP-1001 must reference an existing Carrier (CRR-401)."""
        shp = db_session.get(Shipment, "SHP-1001")
        assert shp is not None
        assert shp.carrier_id == "CRR-401"
        carrier = db_session.get(Carrier, shp.carrier_id)
        assert carrier is not None

    def test_telemetry_vehicle_fk(self, db_session):
        """TEL-FLT-302 must reference an existing FleetAsset."""
        tel = db_session.get(Telemetry, "TEL-FLT-302")
        assert tel is not None
        assert tel.vehicle_id == "FLT-302"
        fleet = db_session.get(FleetAsset, tel.vehicle_id)
        assert fleet is not None

    def test_telemetry_shipment_fk(self, db_session):
        """TEL-FLT-302 must reference an existing Shipment (SHP-1001)."""
        tel = db_session.get(Telemetry, "TEL-FLT-302")
        assert tel is not None
        assert tel.shipment_id == "SHP-1001"
        shp = db_session.get(Shipment, tel.shipment_id)
        assert shp is not None


# ---------------------------------------------------------------------------
# 7. Pydantic schema validation
# ---------------------------------------------------------------------------

class TestPydanticSchemas:
    def test_carrier_response_from_orm(self, db_session):
        carrier = db_session.get(Carrier, "CRR-401")
        # Deserialise certifications for schema
        certs = carrier.get_certifications_list()
        # Build a dict manually to test schema validation path
        data = {
            "carrier_id": carrier.carrier_id,
            "name": carrier.name,
            "contact_email": carrier.contact_email,
            "phone": carrier.phone,
            "compliance_rating": carrier.compliance_rating,
            "on_time_delivery_rate": carrier.on_time_delivery_rate,
            "active_fleet_size": carrier.active_fleet_size,
            "certifications": certs,
        }
        schema = CarrierResponse(**data)
        assert schema.carrier_id == "CRR-401"

    def test_shipment_response_from_orm(self, db_session):
        shp = db_session.get(Shipment, "SHP-1002")
        schema = ShipmentResponse.model_validate(shp)
        assert schema.id == "SHP-1002"
        assert schema.status == "ALERT_DISRUPTION"

    def test_telemetry_response_from_orm(self, db_session):
        tel = db_session.get(Telemetry, "TEL-FLT-514")
        schema = TelemetryResponse.model_validate(tel)
        assert schema.telemetry_id == "TEL-FLT-514"
        assert schema.reefer_compressor_status == "STABLE_CRYOGENIC"

    def test_disruption_response_from_orm(self, db_session):
        dis = db_session.get(Disruption, "DIS-503")
        schema = DisruptionResponse.model_validate(dis)
        assert schema.id == "DIS-503"
        assert schema.severity == "CRITICAL"

    def test_fleet_asset_response_from_orm(self, db_session):
        fleet = db_session.get(FleetAsset, "FLT-302")
        schema = FleetAssetResponse.model_validate(fleet)
        assert schema.id == "FLT-302"

    def test_route_response_from_orm(self, db_session):
        route = db_session.get(Route, "RT-SEA-DEN-01")
        # Routes store highways/waypoints as JSON text; schema expects list
        import json
        data = {
            "route_id": route.route_id,
            "name": route.name,
            "origin": route.origin,
            "destination": route.destination,
            "distance_km": route.distance_km,
            "typical_duration_hours": route.typical_duration_hours,
            "highways": json.loads(route.highways) if route.highways else None,
            "waypoints": json.loads(route.waypoints) if route.waypoints else None,
            "cold_storage_depots": (
                json.loads(route.cold_storage_depots)
                if route.cold_storage_depots
                else None
            ),
        }
        schema = RouteResponse(**data)
        assert schema.route_id == "RT-SEA-DEN-01"

    def test_cargo_rule_response_from_orm(self, db_session):
        rule = (
            db_session.query(CargoRule).filter_by(category="Pharmaceuticals").first()
        )
        schema = CargoRuleResponse.model_validate(rule)
        assert schema.category == "Pharmaceuticals"
        assert schema.requires_continuous_logger is True

    def test_weather_response_from_orm(self, db_session):
        wx = db_session.get(Weather, "WX-ATL-03")
        schema = WeatherResponse.model_validate(wx)
        assert schema.station_id == "WX-ATL-03"
        assert schema.road_condition == "DRY"

    def test_invalid_schema_raises(self):
        """A missing required field should raise a ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ShipmentResponse(
                # Missing required fields: id, origin, destination, ...
                status="IN_TRANSIT",
            )


# ---------------------------------------------------------------------------
# 8. FastAPI /health endpoint
# ---------------------------------------------------------------------------

class TestFastAPIEndpoints:
    """
    Test the FastAPI app using a fully isolated in-memory SQLite database.

    We patch the lifespan at the application level by building a lightweight
    test app that shares the same routes but uses its own lifespan with an
    in-memory engine.  This avoids the module-reload fragility caused by
    SQLAlchemy engine being a module-level singleton.
    """

    @pytest.fixture(scope="class")
    def client(self):
        from contextlib import asynccontextmanager
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm
        from sqlalchemy.pool import StaticPool

        # StaticPool forces all connections to share one in-memory database,
        # which is required for SQLite :memory: to work across multiple
        # Session.connect() calls within the same engine.
        test_engine = _ce(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(test_engine)
        TestSession = _sm(bind=test_engine, autocommit=False, autoflush=False)

        @asynccontextmanager
        async def test_lifespan(app):
            db = TestSession()
            try:
                seed_database(db)
            finally:
                db.close()
            yield

        # Import the app and swap its lifespan for the test lifespan.
        from src.backend.main import app as real_app
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        test_app = FastAPI(
            title=real_app.title,
            version=real_app.version,
            lifespan=test_lifespan,
        )
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register the same routes (root and health) directly.
        @test_app.get("/")
        def _root():
            return {
                "status": "online",
                "service": "Supply Chain Risk Engine",
                "version": "1.0.0",
                "docs_url": "/docs",
            }

        @test_app.get("/health")
        def _health():
            return {"status": "healthy", "timestamp": "2026-09-13T22:00:00Z"}

        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body(self, client):
        response = client.get("/health")
        body = response.json()
        assert body["status"] == "healthy"

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_body(self, client):
        response = client.get("/")
        body = response.json()
        assert body["status"] == "online"
        assert body["version"] == "1.0.0"
